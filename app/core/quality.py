from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class QualityGateResult:
    passed: bool
    pipeline_blocked: bool
    metrics: dict[str, float]
    reasons: list[str]


THRESHOLDS = {
    "missing_rate_max": 0.55,
    "duplicate_rate_max": 0.02,
    "row_count_drop_max": 0.30,
    "psi_mean_max": 0.25,
}


META_COLUMNS = {
    "date",
    "year",
    "month",
    "day",
    "weekday_text",
    "weekday_num",
    "quarter",
    "is_month_start",
    "is_month_end",
    "season",
}


def evaluate_quality_gate(normalized_path: Path, baseline_path: Path | None = None) -> QualityGateResult:
    current = pd.read_csv(normalized_path)
    if current.empty:
        return QualityGateResult(
            passed=False,
            pipeline_blocked=True,
            metrics={
                "missing_rate": 1.0,
                "duplicate_rate": 1.0,
                "row_count_change_rate": -1.0,
                "psi_mean": 1.0,
            },
            reasons=["Normalized dataset is empty."],
        )

    feature_cols = [col for col in current.columns if col not in META_COLUMNS]
    if not feature_cols:
        return QualityGateResult(
            passed=False,
            pipeline_blocked=True,
            metrics={
                "missing_rate": 1.0,
                "duplicate_rate": 1.0,
                "row_count_change_rate": -1.0,
                "psi_mean": 1.0,
            },
            reasons=["No feature columns found after normalization."],
        )

    missing_rate = float(current[feature_cols].isna().mean().mean())
    duplicate_rate = float(current.duplicated(subset=["date"]).mean()) if "date" in current.columns else 0.0
    row_count_change_rate = 0.0
    psi_mean = 0.0

    if baseline_path and baseline_path.exists():
        baseline = pd.read_csv(baseline_path)
        if not baseline.empty:
            row_count_change_rate = float((len(current) - len(baseline)) / max(len(baseline), 1))
            psi_values = _compute_psi_mean(current, baseline, feature_cols)
            psi_mean = float(np.mean(psi_values)) if psi_values else 0.0

    reasons: list[str] = []
    if missing_rate > THRESHOLDS["missing_rate_max"]:
        reasons.append(f"Missing rate {missing_rate:.3f} exceeds {THRESHOLDS['missing_rate_max']:.3f}.")
    if duplicate_rate > THRESHOLDS["duplicate_rate_max"]:
        reasons.append(f"Duplicate rate {duplicate_rate:.3f} exceeds {THRESHOLDS['duplicate_rate_max']:.3f}.")
    if row_count_change_rate < -THRESHOLDS["row_count_drop_max"]:
        reasons.append(
            f"Row count drop {abs(row_count_change_rate):.3f} exceeds {THRESHOLDS['row_count_drop_max']:.3f}."
        )
    if psi_mean > THRESHOLDS["psi_mean_max"]:
        reasons.append(f"PSI mean {psi_mean:.3f} exceeds {THRESHOLDS['psi_mean_max']:.3f}.")

    passed = len(reasons) == 0
    return QualityGateResult(
        passed=passed,
        pipeline_blocked=not passed,
        metrics={
            "missing_rate": round(missing_rate, 6),
            "duplicate_rate": round(duplicate_rate, 6),
            "row_count_change_rate": round(row_count_change_rate, 6),
            "psi_mean": round(psi_mean, 6),
        },
        reasons=reasons,
    )


def _compute_psi_mean(current: pd.DataFrame, baseline: pd.DataFrame, feature_cols: list[str]) -> list[float]:
    psi_values: list[float] = []
    for col in feature_cols:
        c = pd.to_numeric(current[col], errors="coerce").dropna()
        b = pd.to_numeric(baseline[col], errors="coerce").dropna() if col in baseline.columns else pd.Series(dtype=float)
        if c.empty or b.empty:
            continue
        try:
            quantiles = np.unique(np.quantile(b, np.linspace(0, 1, 11)))
            if len(quantiles) < 3:
                continue
            b_hist, _ = np.histogram(b, bins=quantiles)
            c_hist, _ = np.histogram(c, bins=quantiles)
            b_pct = np.clip(b_hist / max(len(b), 1), 1e-6, None)
            c_pct = np.clip(c_hist / max(len(c), 1), 1e-6, None)
            psi = np.sum((c_pct - b_pct) * np.log(c_pct / b_pct))
            psi_values.append(float(psi))
        except Exception:
            continue
    return psi_values

