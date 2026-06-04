from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.core.features import build_feature_frame, normalize_profile
from app.core.settings import FUTURE_PREDICTION_DAYS
from app.core.storage import read_json
from app.core.training import MODEL_REGISTRY_PATH, _latest_usable_normalized_path, get_current_model


@dataclass
class PredictionDateRange:
    target: str
    min_date: str
    max_date: str
    predict_to: str
    rows_available: int
    has_active_model: bool


@lru_cache(maxsize=256)
def get_prediction_date_range(target: str) -> PredictionDateRange:
    """Return the valid prediction date range for a target.

    Result is cached for the lifetime of the process.  The cache is keyed on
    the target string; a new data upload or model training will require a
    server restart (or explicit cache_clear()) to reflect updated ranges.
    """
    normalized_path = _latest_usable_normalized_path()
    if normalized_path is None:
        raise ValueError("No normalized dataset found.")

    df = pd.read_csv(normalized_path).sort_values("date").reset_index(drop=True)
    if target not in df.columns:
        raise ValueError(f"Target '{target}' not found.")

    profile = _active_feature_profile(target)
    feature_df = build_feature_frame(df, target, profile=profile)
    if feature_df.empty:
        raise ValueError(f"No predictable rows for target '{target}'.")

    last_observed = _last_observed_date(df, target)
    predict_to_ts = pd.Timestamp(last_observed) + pd.Timedelta(days=FUTURE_PREDICTION_DAYS)

    has_active = _has_active_model(target)
    return PredictionDateRange(
        target=target,
        min_date=str(feature_df["date"].min()),
        max_date=str(feature_df["date"].max()),
        predict_to=predict_to_ts.strftime("%Y-%m-%d"),
        rows_available=int(len(feature_df)),
        has_active_model=has_active,
    )


def _last_observed_date(df: pd.DataFrame, target: str) -> str:
    series = pd.to_numeric(df[target], errors="coerce")
    last_idx = series.last_valid_index()
    if last_idx is None:
        return str(df["date"].max())
    return str(df.loc[last_idx, "date"])


@lru_cache(maxsize=256)
def _active_feature_profile(target: str) -> str:
    """Cache the active feature profile for a target."""
    try:
        model_entry = get_current_model(target)
        artifact = read_json(Path(model_entry["artifact_path"]))
        return normalize_profile(artifact.get("feature_profile", "step3"))
    except ValueError:
        return "step3"


@lru_cache(maxsize=256)
def _has_active_model(target: str) -> bool:
    """Cache whether a target has an active model."""
    if not MODEL_REGISTRY_PATH.exists():
        return False
    payload = read_json(MODEL_REGISTRY_PATH)
    entries = payload.get("models", {}).get(target, [])
    return any(entry.get("active") for entry in entries)

