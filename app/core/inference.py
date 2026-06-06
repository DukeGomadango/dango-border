from functools import lru_cache
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from app.core.availability import get_prediction_date_range
from app.core.features import build_feature_frame, normalize_profile
from app.core.settings import MAX_PREDICTION_RANGE_DAYS, resolve_model_path
from app.core.storage import read_json
from app.core.targets import TARGETS_PATH
from app.core.training import _latest_usable_normalized_path, get_current_model


@lru_cache(maxsize=1)
def _cached_normalized_path() -> Path | None:
    """Cached wrapper around _latest_usable_normalized_path.

    The result is fixed for the lifetime of the process; a new model training
    run that produces a new CSV will require a server restart or explicit
    cache_clear() to take effect.
    """
    return _latest_usable_normalized_path()


@lru_cache(maxsize=256)
def _cached_read_artifact(artifact_path: str) -> dict:
    """Cache artifact JSON by absolute path string."""
    return read_json(Path(artifact_path))


@lru_cache(maxsize=256)
def _cached_get_model_entry(target: str) -> dict:
    """Cache the active model registry entry for a target."""
    return get_current_model(target)


@lru_cache(maxsize=1)
def _cached_read_csv() -> pd.DataFrame:
    """Load and cache the normalized CSV.  Keyed implicitly via _cached_normalized_path."""
    path = _cached_normalized_path()
    if path is None:
        raise ValueError("No normalized dataset found.")
    return pd.read_csv(path).sort_values("date").reset_index(drop=True)


@lru_cache(maxsize=256)
def _cached_feature_frame(target: str, profile: str) -> pd.DataFrame:
    """Build and cache the feature DataFrame for a (target, profile) pair.

    ``build_feature_frame`` processes the full 1 600-row history with rolling
    operations and takes ~240 ms per call.  Caching by (target, profile) means
    the heavy computation runs only once per server lifetime per tier, saving
    ~240 ms × (n_tiers + 1_tft_base) ≈ 960 ms on every prediction request.
    """
    df = _cached_read_csv()
    return build_feature_frame(df, target, profile=profile)


@lru_cache(maxsize=256)
def _cached_feature_frame_raw(target: str, profile: str) -> pd.DataFrame:
    """Build and cache the raw feature DataFrame with drop_nans=False.

    This is used during inference to perform recursive forecasting without
    losing any rows due to historical NaN values.
    """
    df = _cached_read_csv()
    return build_feature_frame(df, target, profile=profile, drop_nans=False)


def predict_for_date_range(target: str, from_date: str, to_date: str) -> dict[str, object]:
    start = pd.Timestamp(from_date)
    end = pd.Timestamp(to_date)
    if end < start:
        raise ValueError("'to_date' must be on or after 'from_date'.")
    day_count = int((end - start).days) + 1
    if day_count > MAX_PREDICTION_RANGE_DAYS:
        raise ValueError(f"Date range exceeds {MAX_PREDICTION_RANGE_DAYS} days.")

    date_range = get_prediction_date_range(target)
    allowed_min = pd.Timestamp(date_range.min_date)
    allowed_max = pd.Timestamp(date_range.predict_to)
    if start < allowed_min or end > allowed_max:
        raise ValueError(
            f"Dates must be within {date_range.min_date} .. {date_range.predict_to} for target '{target}'."
        )

    # --- Pre-load shared resources ONCE for all dates in this range ---
    _ensure_target_published(target)  # raises if not published
    model_entry = _cached_get_model_entry(target)
    artifact = _cached_read_artifact(model_entry["artifact_path"])
    df = _cached_read_csv()
    if target not in df.columns:
        raise ValueError(f"Target '{target}' not found.")
    profile = normalize_profile(artifact.get("feature_profile", "step3"))
    
    # Retrieve the raw feature frame from cache to avoid rebuilding it from scratch (~50ms -> ~0ms)
    feature_df = _cached_feature_frame_raw(target, profile).copy()
    feature_cols = artifact["feature_columns"]
    model_type = artifact.get("model_type", "linear")
    # Safely impute historical NaNs for all feature columns ONLY for linear models
    if model_type == "linear":
        feature_df[feature_cols] = feature_df[feature_cols].ffill().bfill().fillna(0.0)

    # Pre-load booster or coefficients once
    if model_type == "lightgbm":
        from app.core.model_cache import get_cached_lgbm_booster
        booster = get_cached_lgbm_booster(resolve_model_path(artifact["model_path"]))
        num_iteration = artifact.get("best_iteration")
    else:
        booster = None
        num_iteration = None
        coefs = np.array([artifact["intercept"]] + artifact["coefficients"], dtype=float)

    s_arr = pd.to_numeric(df[target], errors="coerce").to_numpy(copy=True)
    last_valid_idx = pd.to_numeric(df[target], errors="coerce").last_valid_index()
    if last_valid_idx is None:
        raise ValueError(f"Cannot predict for '{target}': no historical values.")
    last_valid_date = pd.Timestamp(df.loc[last_valid_idx, "date"])

    # Recursive forecasting for future dates
    end_date_str = end.strftime("%Y-%m-%d")
    end_idx_list = df[df["date"] == end_date_str].index
    if not end_idx_list.empty:
        end_idx = end_idx_list[0]
    else:
        end_idx = len(df) - 1

    future_features_dict = {}

    if end_idx > last_valid_idx:
        weekday_nums = df["weekday_num"].to_numpy(dtype=int)
        
        for i in range(last_valid_idx + 1, end_idx + 1):
            ts_current = pd.Timestamp(df.loc[i, "date"])
            date_str = ts_current.strftime("%Y-%m-%d")
            x_row = feature_df.iloc[i].copy()

            # Update lag features using NumPy array
            x_row["lag_1"] = s_arr[i - 1] if i - 1 >= 0 else np.nan
            x_row["lag_7"] = s_arr[i - 7] if i - 7 >= 0 else np.nan
            x_row["lag_14"] = s_arr[i - 14] if i - 14 >= 0 else np.nan
            x_row["lag_28"] = s_arr[i - 28] if i - 28 >= 0 else np.nan

            # Update rolling features on NumPy slices
            slice_7 = s_arr[max(0, i - 7):i]
            slice_28 = s_arr[max(0, i - 28):i]
            
            x_row["rolling_mean_7"] = np.nanmean(slice_7) if len(slice_7) > 0 else np.nan
            x_row["rolling_mean_28"] = np.nanmean(slice_28) if len(slice_28) > 0 else np.nan
            x_row["rolling_std_7"] = np.nanstd(slice_7) if len(slice_7) > 0 else np.nan
            x_row["rolling_std_28"] = np.nanstd(slice_28) if len(slice_28) > 0 else np.nan

            # Update weekday seasonal mean using NumPy mask
            current_wk = weekday_nums[i]
            past_wk_mask = weekday_nums[:i] == current_wk
            past_same_wk = s_arr[:i][past_wk_mask]
            x_row["weekday_seasonal_mean"] = np.nanmean(past_same_wk) if len(past_same_wk) > 0 else np.nan

            # Update gap decay features
            days_since = (ts_current - last_valid_date).days
            x_row["days_since_last_obs"] = float(days_since)
            x_row["decay_weight"] = np.exp(-np.log(2) * float(days_since) / 7.0)

            # Update decay-multiplied lags
            if "lag_1_decayed" in x_row:
                x_row["lag_1_decayed"] = x_row["lag_1"] * x_row["decay_weight"]
            if "lag_7_decayed" in x_row:
                x_row["lag_7_decayed"] = x_row["lag_7"] * x_row["decay_weight"]
            if "lag_14_decayed" in x_row:
                x_row["lag_14_decayed"] = x_row["lag_14"] * x_row["decay_weight"]
            if "lag_28_decayed" in x_row:
                x_row["lag_28_decayed"] = x_row["lag_28"] * x_row["decay_weight"]

            # Handle potential NaNs safely (only for linear models)
            if model_type == "linear":
                x_row = x_row.fillna(0.0)

            x = x_row[feature_cols].to_frame().T.astype(float)

            if model_type == "lightgbm":
                if num_iteration is None:
                    p50 = float(booster.predict(x)[0])
                else:
                    p50 = float(booster.predict(x, num_iteration=int(num_iteration))[0])
            else:
                x_design = np.hstack([np.ones((1, 1)), x.to_numpy(dtype=float)])
                p50 = float((x_design @ coefs).item())

            # Propagate prediction to subsequent recursive steps
            s_arr[i] = p50
            
            # Store features in dictionary for fast lookup in the final evaluation loop
            if start <= ts_current <= end:
                future_features_dict[date_str] = x_row[feature_cols]

    predictions: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    for ts in pd.date_range(start, end, freq="D"):
        date = ts.strftime("%Y-%m-%d")
        try:
            if date in future_features_dict:
                x = future_features_dict[date].to_frame().T.astype(float)
            else:
                row = feature_df[feature_df["date"] == date]
                if row.empty:
                    raise ValueError(f"No row found in feature frame for date '{date}'.")
                x = row.iloc[[0]][feature_cols].astype(float)

            if model_type == "lightgbm":
                if num_iteration is None:
                    p50 = float(booster.predict(x)[0])
                else:
                    p50 = float(booster.predict(x, num_iteration=int(num_iteration))[0])
            else:
                x_design = np.hstack([np.ones((1, 1)), x.to_numpy(dtype=float)])
                p50 = float((x_design @ coefs).item())

            p10, p90 = _prediction_interval(p50, artifact)
            # Clip predictions and intervals to be non-negative
            p50_clipped = max(0.0, p50)
            p10_clipped = max(0.0, p10)
            p90_clipped = max(0.0, p90)
            
            evaluation = model_entry.get("evaluation", {})
            predictions.append({
                "target": target,
                "date": date,
                "prediction": round(p50_clipped, 2),
                "interval": {"p10": round(p10_clipped, 2), "p50": round(p50_clipped, 2), "p90": round(p90_clipped, 2)},
                "model_version": model_entry["model_version"],
                "model_type": model_type,
                "quality_status": "ok" if evaluation.get("adopted", True) else "degraded",
                "trained_at": artifact.get("created_at"),
            })
        except ValueError as exc:
            errors.append({"date": date, "error": str(exc)})

    if not predictions:
        raise ValueError("No predictions could be produced for the requested range.")

    return {
        "target": target,
        "from_date": from_date,
        "to_date": to_date,
        "model_version": predictions[-1]["model_version"],
        "model_type": predictions[-1]["model_type"],
        "count": len(predictions),
        "predictions": predictions,
        "errors": errors,
    }


def predict_for_date(target: str, date: str) -> dict[str, object]:
    res = predict_for_date_range(target, date, date)
    if res["errors"]:
        raise ValueError(res["errors"][0]["error"])
    return res["predictions"][0]


def _prediction_interval(p50: float, artifact: dict[str, object]) -> tuple[float, float]:
    calibration = artifact.get("interval_calibration")
    if isinstance(calibration, dict) and calibration.get("method") == "cv_residual_quantile":
        p10_off = float(calibration.get("p10_offset", 0.0))
        p90_off = float(calibration.get("p90_offset", 0.0))
        return p50 + p10_off, p50 + p90_off

    rmse = float(artifact.get("metrics_train", {}).get("rmse", 0.0))
    return p50 - 1.28 * rmse, p50 + 1.28 * rmse


def _season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def _ensure_target_published(target: str) -> None:
    if not TARGETS_PATH.exists():
        raise ValueError("Targets registry not found.")
    payload = read_json(TARGETS_PATH)
    rows = [r for r in payload.get("targets", []) if r.get("target") == target]
    if not rows:
        raise ValueError(f"Target '{target}' not found.")
    row = rows[0]
    if row.get("status") == "blocked":
        raise ValueError(f"Target '{target}' is blocked.")
    if not row.get("publish"):
        raise ValueError(f"Target '{target}' is not published.")
