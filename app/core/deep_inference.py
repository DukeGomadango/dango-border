"""Inference pipeline for deep learning border prediction models.

Loads a trained BorderTFT model and generates multi-step future predictions
for all tiers within a target group, with guaranteed monotonic ordering.

Fast path: ``predict_group_future_cached()`` pulls a pre-loaded model from the
in-memory cache (app.core.model_cache) to avoid repeated disk I/O.
Slow path: ``predict_group_future()`` retains the original load-from-disk
behavior for use in testing or CLI contexts.
"""
from __future__ import annotations

from pathlib import Path

import holidays
import numpy as np
import pandas as pd
import torch

from app.core.deep_models import BorderTFT, ModelConfig
from app.core.deep_training import KNOWN_FUTURE_FEATURES, _discover_target_groups
from app.core.settings import MODELS_DIR, STORAGE_DIR
from app.core.storage import read_json
from app.core.training import _latest_usable_normalized_path, target_to_slug


def _run_inference(
    artifact: dict[str, object],
    model: "BorderTFT",
    target_group: str,
    from_date: str,
    to_date: str,
) -> dict[str, object]:
    """Shared inference logic used by both the cached and cold-load paths.

    Args:
        artifact: decoded artifact JSON dict (scaler stats, feature cols, …).
        model:    pre-loaded BorderTFT instance already in eval() mode.
        target_group: e.g., 'S1'
        from_date: start of forecast window (YYYY-MM-DD)
        to_date: end of forecast window (YYYY-MM-DD)

    Returns:
        Prediction result dict.
    """
    tier_columns = artifact["tier_columns"]
    target_scaler = {k: tuple(v) for k, v in artifact["target_scaler"].items()}
    feature_cols = artifact["feature_cols"]
    future_cols = artifact["future_cols"]
    feature_means = np.array(artifact["feature_means"], dtype=np.float32)
    feature_stds = np.array(artifact["feature_stds"], dtype=np.float32)
    future_means = np.array(artifact["future_means"], dtype=np.float32)
    future_stds = np.array(artifact["future_stds"], dtype=np.float32)
    encoder_len = artifact["training"]["encoder_len"]

    # Load historical data for encoder context (use shared lru_cache from inference module)
    from app.core.inference import _cached_read_csv, _cached_normalized_path
    from app.core.features import build_feature_frame

    if _cached_normalized_path() is None:
        raise ValueError("No normalized dataset found.")

    df = _cached_read_csv()

    # Build historical feature array (from the base tier)
    base_tier = tier_columns[0]
    base_df = build_feature_frame(df, base_tier, profile="step3")

    # Get encoder window: last encoder_len rows of historical data
    hist_features = np.zeros((len(base_df), len(feature_cols)), dtype=np.float32)
    for j, col in enumerate(feature_cols):
        if col in base_df.columns:
            hist_features[:, j] = base_df[col].fillna(0).to_numpy(dtype=np.float32)

    # Apply scaling
    hist_features = (hist_features - feature_means) / feature_stds

    # Take the last encoder_len rows as encoder context
    if len(hist_features) < encoder_len:
        pad_len = encoder_len - len(hist_features)
        hist_features = np.vstack([
            np.zeros((pad_len, len(feature_cols)), dtype=np.float32),
            hist_features,
        ])

    encoder_input = hist_features[-encoder_len:]

    # Build decoder input (known future features)
    forecast_dates = pd.date_range(from_date, to_date, freq="D")
    decoder_len = len(forecast_dates)

    # Generate calendar features for future dates
    future_features = _build_future_calendar_features(forecast_dates, future_cols)
    future_features = (future_features - future_means) / future_stds

    # Run inference – use inference_mode (stricter & faster than no_grad)
    encoder_tensor = torch.tensor(encoder_input, dtype=torch.float32).unsqueeze(0)
    decoder_tensor = torch.tensor(future_features, dtype=torch.float32).unsqueeze(0)

    with torch.inference_mode():
        output = model(encoder_tensor, decoder_tensor)
        # output: (1, decoder_len, n_tiers, n_quantiles)

    predictions_scaled = output.squeeze(0).numpy()

    # Inverse scale predictions
    steps = []
    for t in range(decoder_len):
        date_str = forecast_dates[t].strftime("%Y-%m-%d")
        event_day = ((forecast_dates[t].weekday() - 1) % 7) + 1

        tier_preds: dict[str, dict[str, float]] = {}
        for i, tier in enumerate(tier_columns):
            t_min, t_max = target_scaler[tier]
            p10_raw = float(predictions_scaled[t, i, 0])
            p50_raw = float(predictions_scaled[t, i, 1])
            p90_raw = float(predictions_scaled[t, i, 2])

            p10 = round(p10_raw * (t_max - t_min) + t_min, 2)
            p50 = round(p50_raw * (t_max - t_min) + t_min, 2)
            p90 = round(p90_raw * (t_max - t_min) + t_min, 2)

            # Historical weekday mean
            weekday_num = int(forecast_dates[t].weekday())
            if "weekday_num" in df.columns and tier in df.columns:
                hist_series = df[df["weekday_num"] == weekday_num][tier].dropna()
                hist_mean = round(float(hist_series.mean()), 2) if not hist_series.empty else None
            else:
                hist_mean = None

            tier_preds[tier] = {"p10": p10, "p50": p50, "p90": p90, "historical_mean": hist_mean}

        steps.append({
            "date": date_str,
            "event_day": event_day,
            "predictions": tier_preds,
        })

    return {
        "target_group": target_group,
        "from_date": from_date,
        "to_date": to_date,
        "model_version": artifact["model_version"],
        "model_type": "deep_tft",
        "count": decoder_len,
        "steps": steps,
    }


def predict_group_future_cached(
    target_group: str,
    from_date: str,
    to_date: str,
) -> dict[str, object]:
    """Fast inference path using the in-memory model cache.

    Retrieves the pre-loaded model from ``app.core.model_cache`` and runs
    prediction without any disk I/O.  Raises ``ValueError`` if the model for
    *target_group* was not warmed up at startup.
    """
    from app.core.model_cache import get_cached_entry
    artifact, model = get_cached_entry(target_group)
    return _run_inference(artifact, model, target_group, from_date, to_date)


def predict_group_future(
    target_group: str,
    from_date: str,
    to_date: str,
) -> dict[str, object]:
    """Slow (cold-load) inference path – loads model weights from disk each call.

    Prefer ``predict_group_future_cached()`` for production use.
    This function is retained for CLI scripts and unit tests where the
    in-memory cache has not been warmed up.
    """
    artifact = _load_latest_deep_artifact(target_group)
    model = _load_model(artifact)
    model.eval()
    return _run_inference(artifact, model, target_group, from_date, to_date)


def _build_future_calendar_features(
    dates: pd.DatetimeIndex,
    future_cols: list[str],
) -> np.ndarray:
    """Build known future features from a DatetimeIndex."""
    n = len(dates)

    # Pre-compute JP holidays
    years = range(int(dates.year.min()), int(dates.year.max()) + 1)
    jp_holidays = holidays.Japan(years=years)
    is_holiday = np.array([1 if d.date() in jp_holidays else 0 for d in dates], dtype=np.float32)

    feature_map: dict[str, np.ndarray] = {
        "year": np.array(dates.year, dtype=np.float32),
        "month": np.array(dates.month, dtype=np.float32),
        "day": np.array(dates.day, dtype=np.float32),
        "weekday_num": np.array(dates.weekday, dtype=np.float32),
        "quarter": np.array((dates.month - 1) // 3 + 1, dtype=np.float32),
        "is_month_start": np.array(dates.day == 1, dtype=np.float32),
        "is_month_end": np.array(dates.is_month_end, dtype=np.float32),
        "is_holiday_jp": is_holiday,
        "is_day_before_holiday": np.roll(is_holiday, -1),
        "is_day_after_holiday": np.roll(is_holiday, 1),
    }

    # Event cycle features (IRIAM: Tuesday=start, Monday=end)
    weekday_arr = dates.weekday.to_numpy(dtype=int)
    event_day = ((weekday_arr - 1) % 7) + 1
    feature_map["event_day"] = event_day.astype(np.float32)
    feature_map["event_progress"] = ((event_day - 1) / 6.0).astype(np.float32)
    feature_map["is_event_start"] = (event_day == 1).astype(np.float32)
    feature_map["is_event_end"] = (event_day == 7).astype(np.float32)
    feature_map["is_weekend_in_event"] = ((event_day == 5) | (event_day == 6)).astype(np.float32)

    # Long weekend window (simplified for future: just use weekends + holidays)
    is_weekend = (weekday_arr >= 5).astype(np.float32)
    feature_map["is_long_weekend_window"] = np.clip(is_weekend + is_holiday, 0, 1)

    # Major holiday clusters (GW, Obon, New Year)
    is_gw = np.array([1 if ((d.month == 4 and d.day >= 29) or (d.month == 5 and d.day <= 6)) else 0 for d in dates], dtype=np.float32)
    is_obon = np.array([1 if (d.month == 8 and d.day >= 13 and d.day <= 16) else 0 for d in dates], dtype=np.float32)
    is_ny = np.array([1 if ((d.month == 12 and d.day >= 29) or (d.month == 1 and d.day <= 3)) else 0 for d in dates], dtype=np.float32)

    feature_map["is_golden_week"] = is_gw
    feature_map["is_obon"] = is_obon
    feature_map["is_new_year"] = is_ny

    # Build array in column order
    result = np.zeros((n, len(future_cols)), dtype=np.float32)
    for j, col in enumerate(future_cols):
        if col in feature_map:
            result[:, j] = feature_map[col]
    return result


def _load_latest_deep_artifact(target_group: str) -> dict[str, object]:
    """Load the latest deep model artifact for a target group."""
    slug = target_to_slug(target_group)
    artifact_dir = MODELS_DIR / f"deep-{slug}"
    if not artifact_dir.exists():
        raise ValueError(f"No deep model found for target group '{target_group}'.")

    json_files = sorted(
        [p for p in artifact_dir.glob("*.json") if p.name != "best_params.json"],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    if not json_files:
        raise ValueError(f"No deep model artifact found for target group '{target_group}'.")

    return read_json(json_files[0])


def _load_model(artifact: dict[str, object]) -> BorderTFT:
    """Instantiate and load a trained BorderTFT model from an artifact.

    Used by the cold-load path (``predict_group_future``) and
    ``model_cache.warm_up_all_models``.  The returned model is **not** set to
    eval() here; callers are responsible for that.
    """
    cfg = artifact["config"]
    config = ModelConfig(
        input_dim=cfg["input_dim"],
        future_dim=cfg.get("future_dim", 16),
        d_model=cfg["d_model"],
        n_heads=cfg["n_heads"],
        n_encoder_layers=cfg["n_encoder_layers"],
        n_decoder_layers=cfg["n_decoder_layers"],
        dropout=cfg["dropout"],
        max_encoder_len=cfg["max_encoder_len"],
        max_decoder_len=cfg["max_decoder_len"],
        n_quantiles=cfg["n_quantiles"],
        n_tiers=cfg["n_tiers"],
    )
    model = BorderTFT(config)

    model_path = artifact["model_path"]
    state_dict = torch.load(model_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    return model
