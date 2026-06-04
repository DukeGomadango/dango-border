"""Hybrid ensemble inference blending TFT and LightGBM predictions.

Combines the long-term event cycle and multi-horizon awareness of TFT with the
short-term tracking of LightGBM. Fallbacks gracefully if one of the models is missing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.deep_inference import predict_group_future_cached, _discover_target_groups
from app.core.inference import predict_for_date_range, _cached_read_csv
from app.core.training import target_to_slug


def predict_hybrid(
    target_group: str,
    from_date: str,
    to_date: str,
    w_tft: float = 0.6,
) -> dict[str, object]:
    """Generate hybrid predictions by blending TFT and LightGBM.

    Args:
        target_group: target group name (e.g., 'S1')
        from_date: start date (YYYY-MM-DD)
        to_date: end date (YYYY-MM-DD)
        w_tft: weight of TFT predictions (0.0 to 1.0)

    Returns:
        dict with blended predictions for all tiers, preserving monotonicity.
    """
    if not (0.0 <= w_tft <= 1.0):
        raise ValueError("w_tft must be between 0.0 and 1.0")

    # 1. Load TFT predictions
    tft_success = False
    tft_preds = {}
    try:
        tft_preds = predict_group_future_cached(target_group, from_date, to_date)
        tft_success = True
    except Exception as exc:
        print(f"Warning: TFT model not available for {target_group} ({exc}). Using LightGBM only.")

    # Determine tiers in group using cached DataFrame
    df = _cached_read_csv()
    groups = _discover_target_groups(list(df.columns))
    if target_group not in groups:
        raise ValueError(f"Target group '{target_group}' not found.")
    tier_columns = groups[target_group]

    # 2. Load LightGBM predictions for each tier
    lgbm_success = True
    lgbm_preds = {}
    for tier in tier_columns:
        try:
            lgbm_preds[tier] = predict_for_date_range(tier, from_date, to_date)
        except Exception as exc:
            print(f"Warning: LightGBM model not available for {tier} ({exc}).")
            lgbm_success = False

    # 3. Handle Fallback states
    if not tft_success and not lgbm_success:
        raise ValueError(f"Neither TFT nor LightGBM models are available for target group '{target_group}'.")

    if not tft_success:
        # Fallback to LightGBM only
        return _format_lgbm_only(target_group, from_date, to_date, tier_columns, lgbm_preds)

    if not lgbm_success:
        # Fallback to TFT only
        tft_preds["blending_status"] = "tft_only"
        tft_preds["w_tft"] = 1.0
        return tft_preds

    # 4. Blend predictions (TFT and LightGBM both succeeded)
    forecast_dates = pd.date_range(from_date, to_date, freq="D")
    decoder_len = len(forecast_dates)
    
    steps = []
    for t in range(decoder_len):
        date_str = forecast_dates[t].strftime("%Y-%m-%d")
        event_day = ((forecast_dates[t].weekday() - 1) % 7) + 1

        tier_preds = {}
        tft_step = tft_preds["steps"][t]
        
        for tier in tier_columns:
            # TFT predictions (p10, p50, p90)
            t_p10 = tft_step["predictions"][tier]["p10"]
            t_p50 = tft_step["predictions"][tier]["p50"]
            t_p90 = tft_step["predictions"][tier]["p90"]

            # LightGBM predictions (p10, p50, p90)
            lgbm_step = lgbm_preds[tier]["predictions"][t]
            l_p10 = lgbm_step["interval"]["p10"]
            l_p50 = lgbm_step["prediction"]
            l_p90 = lgbm_step["interval"]["p90"]

            # Weighted blending
            p10 = round(w_tft * t_p10 + (1 - w_tft) * l_p10, 2)
            p50 = round(w_tft * t_p50 + (1 - w_tft) * l_p50, 2)
            p90 = round(w_tft * t_p90 + (1 - w_tft) * l_p90, 2)

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
        "model_version": f"hybrid-{target_to_slug(target_group)}",
        "model_type": "hybrid_ensemble",
        "blending_status": "blended",
        "w_tft": w_tft,
        "count": decoder_len,
        "steps": steps,
    }


def _format_lgbm_only(
    target_group: str,
    from_date: str,
    to_date: str,
    tier_columns: list[str],
    lgbm_preds: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Helper to format LightGBM predictions into a group response format."""
    forecast_dates = pd.date_range(from_date, to_date, freq="D")
    decoder_len = len(forecast_dates)

    steps = []
    for t in range(decoder_len):
        date_str = forecast_dates[t].strftime("%Y-%m-%d")
        event_day = ((forecast_dates[t].weekday() - 1) % 7) + 1

        df = _cached_read_csv()
        tier_preds = {}
        for tier in tier_columns:
            lgbm_step = lgbm_preds[tier]["predictions"][t]
            p10 = lgbm_step["interval"]["p10"]
            p50 = lgbm_step["prediction"]
            p90 = lgbm_step["interval"]["p90"]

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
        "model_version": lgbm_preds[tier_columns[0]]["model_version"],
        "model_type": "lightgbm",
        "blending_status": "lgbm_only",
        "w_tft": 0.0,
        "count": decoder_len,
        "steps": steps,
    }
