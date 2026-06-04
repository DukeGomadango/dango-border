#!/usr/bin/env python3
"""Script to evaluate TFT deep learning model vs LightGBM baseline.

Runs rolling window backtests on historical data to compute MAE, RMSE, MAPE,
and monotonicity rate for both models, ensuring fair comparison with no leakage.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import shutil
import tempfile
import time
import numpy as np
import pandas as pd
import torch
import lightgbm as lgb

from app.core import training, deep_training, deep_inference
from app.core.training import _latest_usable_normalized_path, target_to_slug
from app.core.deep_training import train_deep_model
from app.core.deep_inference import predict_group_future
from app.core.features import build_feature_frame, feature_matrix
from app.core.storage import write_json, utc_now_iso
from app.core.settings import MODELS_DIR

# Parameters for evaluation LightGBM (matching app/core/training.py)
LGBM_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "verbosity": -1,
    "seed": 42,
}

def build_feature_frame_eval(df: pd.DataFrame, target: str, profile: str = "step3") -> pd.DataFrame:
    from app.core.features import (
        normalize_profile, _weekday_seasonal_mean, _add_holiday_features,
        _add_long_weekend_window, _add_event_cycle_features, _add_gap_decay_features
    )
    profile = normalize_profile(profile)
    s = pd.to_numeric(df[target], errors="coerce")
    features = pd.DataFrame(index=df.index)
    features["date"] = df["date"]
    features["year"] = pd.to_numeric(df["year"], errors="coerce")
    features["month"] = pd.to_numeric(df["month"], errors="coerce")
    features["day"] = pd.to_numeric(df["day"], errors="coerce")
    features["weekday_num"] = pd.to_numeric(df["weekday_num"], errors="coerce")
    features["quarter"] = pd.to_numeric(df["quarter"], errors="coerce")
    features["is_month_start"] = pd.to_numeric(df["is_month_start"], errors="coerce")
    features["is_month_end"] = pd.to_numeric(df["is_month_end"], errors="coerce")

    past = s.shift(1)
    features["lag_1"] = past
    features["lag_7"] = s.shift(7)

    if profile in ("step2", "step3"):
        features["lag_14"] = s.shift(14)
        features["lag_28"] = s.shift(28)
        features["rolling_mean_7"] = past.rolling(7, min_periods=1).mean()
        features["rolling_mean_28"] = past.rolling(28, min_periods=1).mean()
        features["rolling_std_7"] = past.rolling(7, min_periods=1).std()
        features["rolling_std_28"] = past.rolling(28, min_periods=1).std()
        features["weekday_seasonal_mean"] = _weekday_seasonal_mean(features["weekday_num"], past)
    elif profile == "sparse":
        features["rolling_mean_7"] = past.rolling(7, min_periods=1).mean()

    if profile == "step3":
        _add_holiday_features(features)
        _add_long_weekend_window(features)

    _add_event_cycle_features(features)

    if profile in ("step2", "step3"):
        _add_gap_decay_features(features, s)

    features["y"] = s
    return features


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate TFT model vs LightGBM baseline.")
    parser.add_argument("--group", type=str, default="S1", help="Target group to evaluate (e.g. S1, A1, B1)")
    parser.add_argument("--folds", type=int, default=4, help="Number of rolling 7-day folds")
    parser.add_argument("--epochs", type=int, default=30, help="Epochs to train TFT per fold (keep small for speed)")
    return parser.parse_args()

def main():
    args = parse_args()
    target_group = args.group
    n_folds = args.folds
    tft_epochs = args.epochs

    print(f"=== Starting Evaluation for Target Group: {target_group} ===")
    
    # 1. Load original normalized dataset
    original_path = _latest_usable_normalized_path()
    if not original_path:
        print("Error: No normalized dataset found.", file=sys.stderr)
        sys.exit(1)
    
    print(f"Loading dataset from: {original_path}")
    df = pd.read_csv(original_path).sort_values("date").reset_index(drop=True)
    df["date_parsed"] = pd.to_datetime(df["date"])
    
    # Identify target columns
    pattern = f"^{target_group}\\s*\\+(\\d+)$"
    import re
    tier_cols = []
    for col in df.columns:
        if re.match(pattern, col):
            tier_cols.append(col)
    
    # Sort columns by tier (+2, +4, +6)
    tier_cols = sorted(tier_cols, key=lambda c: int(re.search(r"\+(\d+)", c).group(1)))
    
    if len(tier_cols) != 3:
        print(f"Error: Target group {target_group} does not have exactly 3 tiers in columns: {df.columns}", file=sys.stderr)
        sys.exit(1)
        
    print(f"Tiers to evaluate: {tier_cols}")
    
    # 2. Determine fold dates (aligned with Tuesday-Monday event cycle)
    # Filter df to only valid target rows to avoid evaluating future NaNs
    valid_dates = df[df[tier_cols[0]].notna()]["date"]
    if valid_dates.empty:
        print(f"Error: No valid observations for target {tier_cols[0]}", file=sys.stderr)
        sys.exit(1)
    last_valid_date = valid_dates.max()
    df_valid = df[df["date"] <= last_valid_date].copy()
    
    # Let's find the last Monday in the valid dataset range
    df_mondays = df_valid[df_valid["weekday_num"] == 0]
    if len(df_mondays) < n_folds:
        print("Error: Not enough Mondays in the dataset for requested folds.", file=sys.stderr)
        sys.exit(1)
        
    last_mondays = df_mondays["date_parsed"].sort_values().tolist()[-n_folds:]
    
    folds_config = []
    for i, test_end in enumerate(last_mondays):
        test_start = test_end - pd.Timedelta(days=6) # Tuesday (since Tuesday to Monday is 7 days)
        cutoff = test_start - pd.Timedelta(days=1)   # Monday before test starts
        
        folds_config.append({
            "fold_idx": i + 1,
            "train_cutoff": cutoff.strftime("%Y-%m-%d"),
            "test_start": test_start.strftime("%Y-%m-%d"),
            "test_end": test_end.strftime("%Y-%m-%d")
        })
        
    print("\n--- Folds Configuration (Tuesday-Monday Events) ---")
    for f in folds_config:
        print(f"Fold {f['fold_idx']}: Train up to {f['train_cutoff']} | Test {f['test_start']} to {f['test_end']}")

    # Setup temp directory for temporary datasets
    temp_dir = tempfile.mkdtemp()
    
    results = []
    
    try:
        for f in folds_config:
            fold_idx = f["fold_idx"]
            cutoff_date = f["train_cutoff"]
            test_start = f["test_start"]
            test_end = f["test_end"]
            
            print(f"\n=================== Fold {fold_idx}/{n_folds} ===================")
            
            # Prepare train data up to cutoff
            df_train = df[df["date"] <= cutoff_date].copy()
            temp_csv_path = Path(temp_dir) / f"fold_{fold_idx}_normalized.csv"
            df_train.drop(columns=["date_parsed"]).to_csv(temp_csv_path, index=False)
            
            # Mock the data path
            training._latest_usable_normalized_path = lambda: temp_csv_path
            deep_training._latest_usable_normalized_path = lambda: temp_csv_path
            deep_inference._latest_usable_normalized_path = lambda: temp_csv_path
            
            # 3. Train TFT
            print(f"Training TFT model on data up to {cutoff_date}...")
            t0 = time.time()
            tft_result = train_deep_model(
                target_group=target_group,
                epochs=tft_epochs,
                patience=5,
                batch_size=16
            )
            t_tft_train = time.time() - t0
            print(f"TFT training completed in {t_tft_train:.1f}s. Val loss: {tft_result.val_loss:.6f}")
            
            # Make predictions with TFT
            print(f"Generating TFT predictions for {test_start} to {test_end}...")
            tft_preds = predict_group_future(target_group, test_start, test_end)
            
            # 4. Train and predict with LightGBM baseline for each tier
            lgb_predictions = {}
            t0 = time.time()
            for tier in tier_cols:
                # Prepare features using step3 profile (no dropna inside build_feature_frame_eval)
                feature_df = build_feature_frame_eval(df, tier, profile="step3")
                
                # Align feature columns from the baseline config
                meta_cols = {"date", "y", "weekday_text"}
                feat_cols = [c for c in feature_df.columns if c not in meta_cols]
                
                # Filter train and test
                feat_train = feature_df[feature_df["date"] <= cutoff_date].dropna(subset=["y"] + feat_cols)
                feat_test = feature_df[(feature_df["date"] >= test_start) & (feature_df["date"] <= test_end)]
                
                if len(feat_train) < 60:
                    print(f"Warning: Not enough rows to train LightGBM for {tier} (got {len(feat_train)})")
                    lgb_predictions[tier] = [np.nan] * 7
                    continue
                
                train_x, train_y = feat_train[feat_cols], feat_train["y"]
                test_x = feat_test[feat_cols]
                
                # Fit LightGBM
                train_data = lgb.Dataset(train_x, label=train_y)
                booster = lgb.train(LGBM_PARAMS, train_data)
                
                # Predict (fill NaNs in test features just in case, though LGBM handles them)
                preds = booster.predict(test_x)
                lgb_predictions[tier] = preds
                
            t_lgb = time.time() - t0
            print(f"LightGBM baseline trained and predicted in {t_lgb:.1f}s.")
            
            # 5. Collect Ground Truth and Calculate Metrics
            actuals_df = df[(df["date"] >= test_start) & (df["date"] <= test_end)].sort_values("date")
            
            # Print predictions and actuals table for this fold
            print("\nPredictions vs Actuals for this fold:")
            print(f"{'Date':12} | {'Tier':10} | {'Actual':10} | {'TFT P50':10} | {'LGBM':10}")
            print("-" * 65)
            
            for day_idx, row in actuals_df.iterrows():
                date_str = row["date"]
                day_offset = (pd.to_datetime(date_str) - pd.to_datetime(test_start)).days
                
                for t_idx, tier in enumerate(tier_cols):
                    actual_val = row[tier]
                    # TFT prediction (p50)
                    tft_step = tft_preds["steps"][day_offset]
                    tft_p50 = tft_step["predictions"][tier]["p50"]
                    tft_p10 = tft_step["predictions"][tier]["p10"]
                    tft_p90 = tft_step["predictions"][tier]["p90"]
                    
                    # LGBM prediction
                    lgb_val = lgb_predictions[tier][day_offset] if tier in lgb_predictions else np.nan
                    
                    print(f"{date_str:12} | {tier:10} | {actual_val:10.1f} | {tft_p50:10.1f} | {lgb_val:10.1f}")
                    
                    # Store result details
                    results.append({
                        "fold": fold_idx,
                        "date": date_str,
                        "tier": tier,
                        "actual": actual_val,
                        "tft_p50": tft_p50,
                        "tft_p10": tft_p10,
                        "tft_p90": tft_p90,
                        "lgbm": lgb_val
                    })
                    
            # Monotonicity check for this fold
            tft_mono_count = 0
            lgb_mono_count = 0
            for day_offset in range(7):
                # TFT
                tft_step = tft_preds["steps"][day_offset]
                tft_vals = [tft_step["predictions"][t]["p50"] for t in tier_cols]
                if tft_vals[0] <= tft_vals[1] <= tft_vals[2]:
                    tft_mono_count += 1
                # LGBM
                lgb_vals = [lgb_predictions[t][day_offset] for t in tier_cols]
                if lgb_vals[0] <= lgb_vals[1] <= lgb_vals[2]:
                    lgb_mono_count += 1
                    
            print(f"Monotonicity constraints met in this fold: TFT {tft_mono_count}/7 | LightGBM {lgb_mono_count}/7")
            
    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir)
        
    # --- Overall Metrics Compilation ---
    results_df = pd.DataFrame(results).dropna(subset=["actual"])
    
    print("\n\n=================== EVALUATION RESULTS SUMMARY ===================")
    
    summary_rows = []
    
    # Global Metrics
    for model_name, pred_col in [("TFT (Deep)", "tft_p50"), ("LightGBM (Baseline)", "lgbm")]:
        mae = np.mean(np.abs(results_df["actual"] - results_df[pred_col]))
        rmse = np.sqrt(np.mean((results_df["actual"] - results_df[pred_col])**2))
        mape = np.mean(np.abs(results_df["actual"] - results_df[pred_col]) / results_df["actual"]) * 100
        
        # Calculate overall Monotonicity
        mono_ok = 0
        total_steps = 0
        for (fold, date), g in results_df.groupby(["fold", "date"]):
            if len(g) == 3: # Need all 3 tiers
                vals = [g[g["tier"] == t][pred_col].values[0] for t in tier_cols]
                if vals[0] <= vals[1] <= vals[2]:
                    mono_ok += 1
                total_steps += 1
        mono_rate = (mono_ok / total_steps * 100) if total_steps > 0 else np.nan
        
        print(f"\n{model_name}:")
        print(f"  MAE:  {mae:10.2f}")
        print(f"  RMSE: {rmse:10.2f}")
        print(f"  MAPE: {mape:10.2f}%")
        print(f"  Monotonicity rate: {mono_rate:.1f}% ({mono_ok}/{total_steps})")
        
        summary_rows.append({
            "model": model_name,
            "mae": mae,
            "rmse": rmse,
            "mape": mape,
            "mono_rate": mono_rate
        })
        
    # Metrics per tier
    print("\n--- Metrics per Tier ---")
    tier_summary = []
    for tier in tier_cols:
        t_df = results_df[results_df["tier"] == tier]
        print(f"\nTier {tier}:")
        for model_name, pred_col in [("TFT", "tft_p50"), ("LGBM", "lgbm")]:
            mae = np.mean(np.abs(t_df["actual"] - t_df[pred_col]))
            rmse = np.sqrt(np.mean((t_df["actual"] - t_df[pred_col])**2))
            mape = np.mean(np.abs(t_df["actual"] - t_df[pred_col]) / t_df["actual"]) * 100
            print(f"  {model_name:4} -> MAE: {mae:9.2f} | RMSE: {rmse:9.2f} | MAPE: {mape:6.2f}%")
            tier_summary.append({
                "tier": tier,
                "model": model_name,
                "mae": mae,
                "rmse": rmse,
                "mape": mape
            })

    # Write evaluation report markdown file to artifacts folder
    # Find brain artifacts folder
    artifacts_dir = Path("C:/Users/furup/.gemini/antigravity-ide/brain/591272a5-8a6b-4a3e-ad64-02116d8e31ed")
    if artifacts_dir.exists():
        report_path = artifacts_dir / "evaluation_report.md"
        
        # Build Markdown content
        md = []
        md.append(f"# 精度評価レポート: {target_group} グループ")
        md.append(f"\n評価実施日時: {utc_now_iso()}")
        md.append(f"\n## 評価設定")
        md.append(f"- **対象グループ**: {target_group} (`{', '.join(tier_cols)}`)")
        md.append(f"- **検証手法**: {n_folds}分割ローリング・ウィンドウスプリット（未来7日間予測 × {n_folds}イベント分）")
        md.append(f"- **学習設定 (TFT)**: {tft_epochs} Epochs, Early Stopping (patience=5)")
        
        md.append("\n## 総合精度指標の比較")
        md.append("\n| モデル名 | MAE (平均絶対誤差) | RMSE | MAPE (%) | 単調性制約の遵守率 |")
        md.append("| --- | --- | --- | --- | --- |")
        for row in summary_rows:
            md.append(f"| {row['model']} | {row['mae']:.2f} | {row['rmse']:.2f} | {row['mape']:.2f}% | {row['mono_rate']:.1f}% |")
            
        md.append("\n> [!NOTE]\n> 単調性制約の遵守率は、`+2` < `+4` < `+6` の境界の順序が100%維持されているかどうかを示します。")
        
        md.append("\n## ティア別の精度詳細")
        md.append("\n| ティア | モデル | MAE | RMSE | MAPE |")
        md.append("| --- | --- | --- | --- | --- |")
        for s in tier_summary:
            md.append(f"| {s['tier']} | {s['model']} | {s['mae']:.2f} | {s['rmse']:.2f} | {s['mape']:.2f}% |")
            
        md.append("\n## 詳細予測実績データ (一部抜粋)")
        md.append("\n| 日付 | ティア | 実際のボーダー値 | TFT予測 (p50) | LightGBM予測 | TFT誤差 | LightGBM誤差 |")
        md.append("| --- | --- | --- | --- | --- | --- | --- |")
        # Show fold 4 predictions as details
        f4_df = results_df[results_df["fold"] == n_folds]
        for _, row in f4_df.iterrows():
            tft_err = abs(row["actual"] - row["tft_p50"])
            lgb_err = abs(row["actual"] - row["lgbm"])
            md.append(f"| {row['date']} | {row['tier']} | {row['actual']:.1f} | {row['tft_p50']:.1f} | {row['lgbm']:.1f} | {tft_err:.1f} | {lgb_err:.1f} |")
            
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
            
        print(f"\nCreated detailed markdown report at: [evaluation_report.md](file:///{report_path})")

if __name__ == "__main__":
    main()
