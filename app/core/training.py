import re
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from app.core.features import (
    FEATURES_VERSION,
    STEP_PROFILES,
    build_feature_frame,
    feature_matrix,
    normalize_profile,
)
from app.core.settings import JOBS_DIR, MODELS_DIR, STORAGE_DIR
from app.core.storage import read_json, utc_now_iso, write_json
from app.core.targets import TARGETS_PATH


MODEL_REGISTRY_PATH = STORAGE_DIR / "model_versions.json"
TRAINING_SEED = 42
CV_TRAIN_FRACTIONS = (0.7, 0.8, 0.9)
MIN_TRAIN_ROWS = 80
MIN_TRAIN_ROWS_SPARSE = 60
MIN_IMPROVEMENT_RATE = 0.10
FINAL_HOLDOUT_FRACTION = 0.10

LGBM_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "verbosity": -1,
    "seed": TRAINING_SEED,
}


@dataclass
class EvaluationResult:
    model_type: str
    cv_mae: float
    cv_rmse: float
    baseline_mae: float
    baseline_rmse: float
    improvement_rate: float
    adopted: bool
    fold_metrics: list[dict[str, float]]
    interval_p10_offset: float = 0.0
    interval_p90_offset: float = 0.0


@dataclass
class TrainResult:
    target: str
    model_version: str
    artifact_path: Path
    rows_train: int
    metrics: dict[str, float]
    adopted: bool
    model_type: str
    evaluation: EvaluationResult
    feature_profile: str


def train_target_model(
    target: str,
    feature_profile: str = "auto_steps",
    strategy: str = "auto",
) -> TrainResult:
    if strategy not in {"auto", "linear", "lightgbm"}:
        raise ValueError("strategy must be one of: auto, linear, lightgbm")
    if feature_profile not in {"auto_steps", "step1", "step2", "step3", "sparse", "full"}:
        raise ValueError(
            "feature_profile must be one of: auto_steps, step1, step2, step3, sparse, full"
        )

    normalized_path = _latest_usable_normalized_path()
    if normalized_path is None:
        raise ValueError("No normalized dataset found. Upload and process dataset first.")

    df = pd.read_csv(normalized_path).sort_values("date").reset_index(drop=True)
    if target not in df.columns:
        raise ValueError(f"Target '{target}' not found in normalized dataset.")

    _ensure_target_allowed(target)

    if feature_profile == "auto_steps":
        resolved_profile, feature_df, model_type, evaluation = _select_auto_steps_profile(
            df, target, strategy
        )
    else:
        resolved_profile = normalize_profile(feature_profile)
        feature_df = _training_frame(df, target, resolved_profile)
        min_rows = _min_rows_for_profile(resolved_profile)
        if len(feature_df) < min_rows:
            raise ValueError(
                f"Not enough training rows for target '{target}' "
                f"(profile={resolved_profile}, need >= {min_rows})."
            )
        model_type, evaluation = _evaluate_strategy(strategy, feature_df)

    model_version = f"{target_to_slug(target)}-{utc_now_iso().replace(':', '').replace('-', '')}"
    artifact_dir = MODELS_DIR / target_to_slug(target)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{model_version}.json"

    x_df, y_series = feature_matrix(feature_df)
    metrics_train, artifact_extra = _fit_and_serialize(
        model_type=model_type,
        x_df=x_df,
        y_series=y_series,
        artifact_dir=artifact_dir,
        model_version=model_version,
    )

    artifact = {
        "target": target,
        "model_version": model_version,
        "model_type": model_type,
        "created_at": utc_now_iso(),
        "seed": TRAINING_SEED,
        "source_dataset": str(normalized_path),
        "feature_profile": resolved_profile,
        "features_version": FEATURES_VERSION,
        "strategy": strategy,
        "feature_columns": list(x_df.columns),
        "rows_train": int(len(feature_df)),
        "metrics_train": metrics_train,
        "interval_calibration": {
            "method": "cv_residual_quantile",
            "p10_offset": evaluation.interval_p10_offset,
            "p90_offset": evaluation.interval_p90_offset,
        },
        "evaluation": {
            "model_type": evaluation.model_type,
            "cv_mae": evaluation.cv_mae,
            "cv_rmse": evaluation.cv_rmse,
            "baseline_mae": evaluation.baseline_mae,
            "baseline_rmse": evaluation.baseline_rmse,
            "improvement_rate": evaluation.improvement_rate,
            "adopted": evaluation.adopted,
            "fold_metrics": evaluation.fold_metrics,
            "min_improvement_rate": MIN_IMPROVEMENT_RATE,
        },
        **artifact_extra,
    }
    write_json(artifact_path, artifact)
    _update_model_registry(
        target=target,
        model_version=model_version,
        artifact_path=artifact_path,
        metrics=metrics_train,
        evaluation=evaluation,
        model_type=model_type,
    )

    return TrainResult(
        target=target,
        model_version=model_version,
        artifact_path=artifact_path,
        rows_train=int(len(feature_df)),
        metrics=metrics_train,
        adopted=evaluation.adopted,
        model_type=model_type,
        evaluation=evaluation,
        feature_profile=resolved_profile,
    )


def train_all_publishable_targets() -> dict[str, list[dict[str, object]]]:
    targets_payload = read_json(TARGETS_PATH) if TARGETS_PATH.exists() else {}
    target_rows = targets_payload.get("targets", [])
    enabled_targets = [t["target"] for t in target_rows if t.get("publish") is True]

    results: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for target in enabled_targets:
        try:
            trained = train_target_model(target, feature_profile="auto_steps", strategy="auto")
            results.append(
                {
                    "target": trained.target,
                    "model_version": trained.model_version,
                    "model_type": trained.model_type,
                    "feature_profile": trained.feature_profile,
                    "artifact_path": str(trained.artifact_path),
                    "rows_train": trained.rows_train,
                    "metrics": trained.metrics,
                    "adopted": trained.adopted,
                    "improvement_rate": trained.evaluation.improvement_rate,
                }
            )
        except Exception as exc:
            errors.append({"target": target, "error": str(exc)})

    return {"results": results, "errors": errors}


def get_current_model(target: str) -> dict[str, object]:
    if not MODEL_REGISTRY_PATH.exists():
        raise ValueError("Model registry not found.")
    payload = read_json(MODEL_REGISTRY_PATH)
    entries = payload.get("models", {}).get(target, [])
    active = [entry for entry in entries if entry.get("active")]
    if not active:
        raise ValueError(f"No active model for target '{target}'.")
    return active[0]


def list_model_versions(target: str) -> list[dict[str, object]]:
    payload = _load_registry()
    entries = payload.get("models", {}).get(target, [])
    if not entries:
        raise ValueError(f"No model versions found for target '{target}'.")
    return entries


def activate_model_version(target: str, model_version: str) -> dict[str, object]:
    payload = _load_registry()
    entries = payload.get("models", {}).get(target, [])
    if not entries:
        raise ValueError(f"No model versions found for target '{target}'.")

    found = None
    for entry in entries:
        if entry.get("model_version") == model_version:
            found = entry
            break
    if found is None:
        raise ValueError(f"Model version '{model_version}' not found for target '{target}'.")

    if not Path(found["artifact_path"]).exists():
        raise ValueError(f"Artifact not found for version '{model_version}'.")

    for entry in entries:
        entry["active"] = entry.get("model_version") == model_version
    payload["models"][target] = entries
    payload["updated_at"] = utc_now_iso()
    write_json(MODEL_REGISTRY_PATH, payload)
    return found


def rollback_model(target: str) -> dict[str, object]:
    payload = _load_registry()
    entries = payload.get("models", {}).get(target, [])
    if len(entries) < 2:
        raise ValueError(f"No previous model version available for target '{target}'.")

    active_idx = next((i for i, e in enumerate(entries) if e.get("active")), len(entries) - 1)
    for i in range(active_idx - 1, -1, -1):
        candidate = entries[i]
        if candidate.get("evaluation", {}).get("adopted", False):
            return activate_model_version(target, candidate["model_version"])

    previous = entries[active_idx - 1]
    return activate_model_version(target, previous["model_version"])


def _select_auto_steps_profile(
    df: pd.DataFrame, target: str, strategy: str
) -> tuple[str, pd.DataFrame, str, EvaluationResult]:
    best: tuple[str, pd.DataFrame, str, EvaluationResult] | None = None

    for step in STEP_PROFILES:
        profile = normalize_profile(step)
        min_rows = _min_rows_for_profile(profile)
        feature_df = _training_frame(df, target, profile)
        if len(feature_df) < min_rows:
            continue
        try:
            model_type, evaluation = _evaluate_strategy(strategy, feature_df)
        except ValueError:
            continue
        if not evaluation.adopted:
            continue
        if best is None or evaluation.cv_mae < best[3].cv_mae:
            best = (profile, feature_df, model_type, evaluation)

    if best is not None:
        return best

    profile = "sparse"
    min_rows = _min_rows_for_profile(profile)
    feature_df = _training_frame(df, target, profile)
    if len(feature_df) < min_rows:
        raise ValueError(
            f"Not enough training rows for target '{target}' "
            f"(auto_steps and sparse need >= {min_rows})."
        )
    model_type, evaluation = _evaluate_strategy(strategy, feature_df)
    return profile, feature_df, model_type, evaluation


def _evaluate_strategy(strategy: str, feature_df: pd.DataFrame) -> tuple[str, EvaluationResult]:
    if strategy == "auto":
        eval_linear = _evaluate_with_cv_linear(feature_df)
        eval_lgb = _evaluate_with_cv_lightgbm(feature_df)
        return _pick_champion(eval_linear, eval_lgb)
    if strategy == "linear":
        return "linear", _evaluate_with_cv_linear(feature_df)
    return "lightgbm", _evaluate_with_cv_lightgbm(feature_df)


def _training_frame(df: pd.DataFrame, target: str, profile: str) -> pd.DataFrame:
    frame = build_feature_frame(df, target, profile=profile)
    return frame[frame["y"].notna()].reset_index(drop=True)


def _min_rows_for_profile(profile: str) -> int:
    if profile in ("step1", "sparse"):
        return MIN_TRAIN_ROWS_SPARSE
    return MIN_TRAIN_ROWS


def _pick_champion(
    eval_linear: EvaluationResult, eval_lgb: EvaluationResult
) -> tuple[str, EvaluationResult]:
    candidates: list[tuple[str, EvaluationResult]] = [
        ("linear", eval_linear),
        ("lightgbm", eval_lgb),
    ]
    adopted = [item for item in candidates if item[1].adopted]
    if adopted:
        model_type, evaluation = min(adopted, key=lambda item: item[1].cv_mae)
        return model_type, evaluation
    model_type, evaluation = min(candidates, key=lambda item: item[1].cv_mae)
    return model_type, evaluation


def _evaluate_with_cv_linear(feature_df: pd.DataFrame) -> EvaluationResult:
    return _evaluate_with_cv(feature_df, model_type="linear", fold_evaluator=_evaluate_fold_linear)


def _evaluate_with_cv_lightgbm(feature_df: pd.DataFrame) -> EvaluationResult:
    return _evaluate_with_cv(feature_df, model_type="lightgbm", fold_evaluator=_evaluate_fold_lightgbm)


def _evaluate_with_cv(
    feature_df: pd.DataFrame,
    model_type: str,
    fold_evaluator,
) -> EvaluationResult:
    n = len(feature_df)
    model_maes: list[float] = []
    model_rmses: list[float] = []
    baseline_maes: list[float] = []
    baseline_rmses: list[float] = []
    fold_metrics: list[dict[str, float]] = []
    all_residuals: list[float] = []

    for fold_idx, train_frac in enumerate(CV_TRAIN_FRACTIONS):
        train_end = int(n * train_frac)
        if train_end < MIN_TRAIN_ROWS:
            continue
        val_df = feature_df.iloc[train_end:]
        train_df = feature_df.iloc[:train_end]
        if len(val_df) < 5:
            continue

        fold_eval = fold_evaluator(train_df, val_df)
        model_maes.append(fold_eval["model_mae"])
        model_rmses.append(fold_eval["model_rmse"])
        baseline_maes.append(fold_eval["baseline_mae"])
        baseline_rmses.append(fold_eval["baseline_rmse"])
        fold_metrics.append({k: v for k, v in fold_eval.items() if k != "residuals"})
        all_residuals.extend(fold_eval.get("residuals", []))

    if not model_maes:
        raise ValueError("Time-series CV could not produce any valid folds.")

    cv_mae = float(np.mean(model_maes))
    cv_rmse = float(np.mean(model_rmses))
    baseline_mae = float(np.mean(baseline_maes))
    baseline_rmse = float(np.mean(baseline_rmses))

    if baseline_mae <= 0:
        improvement_rate = 0.0
        adopted = False
    else:
        improvement_rate = float((baseline_mae - cv_mae) / baseline_mae)
        adopted = improvement_rate >= MIN_IMPROVEMENT_RATE

    interval_p10_offset = float(np.quantile(all_residuals, 0.10)) if all_residuals else 0.0
    interval_p90_offset = float(np.quantile(all_residuals, 0.90)) if all_residuals else 0.0

    return EvaluationResult(
        model_type=model_type,
        cv_mae=round(cv_mae, 6),
        cv_rmse=round(cv_rmse, 6),
        baseline_mae=round(baseline_mae, 6),
        baseline_rmse=round(baseline_rmse, 6),
        improvement_rate=round(improvement_rate, 6),
        adopted=adopted,
        fold_metrics=fold_metrics,
        interval_p10_offset=round(interval_p10_offset, 6),
        interval_p90_offset=round(interval_p90_offset, 6),
    )


def _evaluate_fold_linear(train_df: pd.DataFrame, val_df: pd.DataFrame) -> dict[str, float]:
    x_train, y_train = feature_matrix(train_df)
    x_val, y_val = feature_matrix(val_df)
    x_train_design = np.hstack([np.ones((len(x_train), 1)), x_train.to_numpy(dtype=float)])
    coefs, _, _, _ = np.linalg.lstsq(x_train_design, y_train.to_numpy(dtype=float), rcond=None)
    x_val_design = np.hstack([np.ones((len(x_val), 1)), x_val.to_numpy(dtype=float)])
    y_pred = x_val_design @ coefs
    y_val_arr = y_val.to_numpy(dtype=float)
    return _metrics_from_predictions(y_val_arr, y_pred, val_df)


def _evaluate_fold_lightgbm(train_df: pd.DataFrame, val_df: pd.DataFrame) -> dict[str, float]:
    x_train, y_train = feature_matrix(train_df)
    x_val, y_val = feature_matrix(val_df)
    train_set = lgb.Dataset(x_train, label=y_train)
    val_set = lgb.Dataset(x_val, label=y_val, reference=train_set)
    booster = lgb.train(
        LGBM_PARAMS,
        train_set,
        num_boost_round=300,
        valid_sets=[val_set],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
    )
    y_pred = booster.predict(x_val, num_iteration=booster.best_iteration)
    return _metrics_from_predictions(y_val.to_numpy(dtype=float), y_pred, val_df)


def _metrics_from_predictions(y_val: np.ndarray, y_pred: np.ndarray, val_df: pd.DataFrame) -> dict[str, float]:
    baseline_pred = val_df["lag_7"].to_numpy(dtype=float)
    valid_mask = ~np.isnan(baseline_pred)
    if not valid_mask.any():
        baseline_pred = val_df["lag_1"].to_numpy(dtype=float)
        valid_mask = ~np.isnan(baseline_pred)

    y_val_valid = y_val[valid_mask]
    y_pred_valid = y_pred[valid_mask]
    baseline_valid = baseline_pred[valid_mask]
    residuals = (y_val_valid - y_pred_valid).tolist()

    return {
        "model_mae": round(float(np.mean(np.abs(y_val_valid - y_pred_valid))), 6),
        "model_rmse": round(float(np.sqrt(np.mean((y_val_valid - y_pred_valid) ** 2))), 6),
        "baseline_mae": round(float(np.mean(np.abs(y_val_valid - baseline_valid))), 6),
        "baseline_rmse": round(float(np.sqrt(np.mean((y_val_valid - baseline_valid) ** 2))), 6),
        "residuals": residuals,
    }


def _fit_and_serialize(
    model_type: str,
    x_df: pd.DataFrame,
    y_series: pd.Series,
    artifact_dir: Path,
    model_version: str,
) -> tuple[dict[str, float], dict[str, object]]:
    y = y_series.to_numpy(dtype=float)
    if model_type == "linear":
        x_design = np.hstack([np.ones((len(x_df), 1)), x_df.to_numpy(dtype=float)])
        coefs, _, _, _ = np.linalg.lstsq(x_design, y, rcond=None)
        y_pred = x_design @ coefs
        return (
            {
                "mae": round(float(np.mean(np.abs(y - y_pred))), 6),
                "rmse": round(float(np.sqrt(np.mean((y - y_pred) ** 2))), 6),
            },
            {
                "intercept": float(coefs[0]),
                "coefficients": [float(v) for v in coefs[1:]],
            },
        )

    model_path = artifact_dir / f"{model_version}.lgb.txt"
    n = len(x_df)
    val_size = max(5, int(n * FINAL_HOLDOUT_FRACTION))
    extra: dict[str, object] = {"model_path": str(model_path)}

    if n > MIN_TRAIN_ROWS and val_size < n - 10:
        x_train = x_df.iloc[:-val_size]
        y_train = y_series.iloc[:-val_size]
        x_val = x_df.iloc[-val_size:]
        y_val = y_series.iloc[-val_size:]
        train_set = lgb.Dataset(x_train, label=y_train)
        val_set = lgb.Dataset(x_val, label=y_val, reference=train_set)
        booster = lgb.train(
            LGBM_PARAMS,
            train_set,
            num_boost_round=300,
            valid_sets=[val_set],
            callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
        )
        best_iteration = int(booster.best_iteration)
        extra["best_iteration"] = best_iteration
        y_pred = booster.predict(x_df, num_iteration=best_iteration)
    else:
        train_set = lgb.Dataset(x_df, label=y_series)
        booster = lgb.train(LGBM_PARAMS, train_set, num_boost_round=300)
        extra["best_iteration"] = 300
        y_pred = booster.predict(x_df)

    booster.save_model(str(model_path))
    return (
        {
            "mae": round(float(np.mean(np.abs(y - y_pred))), 6),
            "rmse": round(float(np.sqrt(np.mean((y - y_pred) ** 2))), 6),
        },
        extra,
    )


def _latest_usable_normalized_path() -> Path | None:
    latest_path: Path | None = None
    latest_updated: str | None = None
    for job_file in JOBS_DIR.glob("*.json"):
        payload = read_json(job_file)
        normalized = payload.get("normalized_dataset_path")
        status = payload.get("status")
        blocked = bool(payload.get("pipeline_blocked", False))
        if status != "completed" or blocked or not normalized:
            continue
        if not Path(normalized).exists():
            continue
        updated_at = payload.get("updated_at", "")
        if latest_updated is None or updated_at > latest_updated:
            latest_updated = updated_at
            latest_path = Path(normalized)
    if latest_path is not None:
        return latest_path

    fallback_files = sorted(JOBS_DIR.glob("*_normalized.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if fallback_files:
        return fallback_files[0]
    return None


def _ensure_target_allowed(target: str) -> None:
    if not TARGETS_PATH.exists():
        raise ValueError("Targets registry not found.")
    payload = read_json(TARGETS_PATH)
    candidates = [row for row in payload.get("targets", []) if row.get("target") == target]
    if not candidates:
        raise ValueError(f"Target '{target}' not found in targets registry.")
    target_row = candidates[0]
    if target_row.get("status") == "blocked":
        raise ValueError(f"Target '{target}' is blocked and cannot be trained.")


def _load_registry() -> dict[str, object]:
    if not MODEL_REGISTRY_PATH.exists():
        raise ValueError("Model registry not found.")
    return read_json(MODEL_REGISTRY_PATH)


def _update_model_registry(
    target: str,
    model_version: str,
    artifact_path: Path,
    metrics: dict[str, float],
    evaluation: EvaluationResult,
    model_type: str,
) -> None:
    payload = {"updated_at": utc_now_iso(), "models": {}}
    if MODEL_REGISTRY_PATH.exists():
        payload = read_json(MODEL_REGISTRY_PATH)
        payload.setdefault("models", {})

    entries = payload["models"].get(target, [])
    if evaluation.adopted:
        for entry in entries:
            entry["active"] = False

    entries.append(
        {
            "target": target,
            "model_version": model_version,
            "model_type": model_type,
            "artifact_path": str(artifact_path),
            "metrics": metrics,
            "evaluation": {
                "model_type": evaluation.model_type,
                "cv_mae": evaluation.cv_mae,
                "cv_rmse": evaluation.cv_rmse,
                "baseline_mae": evaluation.baseline_mae,
                "baseline_rmse": evaluation.baseline_rmse,
                "improvement_rate": evaluation.improvement_rate,
                "adopted": evaluation.adopted,
            },
            "active": evaluation.adopted,
            "created_at": utc_now_iso(),
        }
    )
    payload["models"][target] = entries
    payload["updated_at"] = utc_now_iso()
    write_json(MODEL_REGISTRY_PATH, payload)


def target_to_slug(target: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", target.strip()).strip("-").lower()


_build_feature_frame = build_feature_frame
