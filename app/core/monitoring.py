import json
from pathlib import Path

import pandas as pd

from app.core.inference import predict_for_date
from app.core.settings import MONITORING_DIR
from app.core.storage import read_json, utc_now_iso, write_json
from app.core.training import MODEL_REGISTRY_PATH, _latest_usable_normalized_path, get_current_model

PREDICTIONS_LOG = MONITORING_DIR / "predictions.jsonl"
ERRORS_LOG = MONITORING_DIR / "accuracy.jsonl"


def log_prediction_served(
    target: str,
    date: str,
    prediction: float,
    model_version: str,
    model_type: str,
) -> None:
    MONITORING_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "target": target,
        "date": date,
        "prediction": prediction,
        "model_version": model_version,
        "model_type": model_type,
        "logged_at": utc_now_iso(),
    }
    with PREDICTIONS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def reconcile_prediction_accuracy(normalized_path: Path | None = None) -> dict[str, object]:
    path = normalized_path or _latest_usable_normalized_path()
    if path is None:
        raise ValueError("No normalized dataset found.")

    if not PREDICTIONS_LOG.exists():
        return {"matched": 0, "written": 0, "message": "No prediction log found."}

    df = pd.read_csv(path)
    pending = _load_pending_predictions()
    matched = 0
    written = 0
    remaining: list[dict[str, object]] = []

    for record in pending:
        target = str(record["target"])
        date = str(record["date"])
        if target not in df.columns:
            remaining.append(record)
            continue
        rows = df[df["date"] == date]
        if rows.empty:
            remaining.append(record)
            continue
        actual = pd.to_numeric(rows[target].iloc[0], errors="coerce")
        if pd.isna(actual):
            remaining.append(record)
            continue

        predicted = float(record["prediction"])
        error = float(actual - predicted)
        matched += 1
        _append_accuracy(
            {
                "target": target,
                "date": date,
                "actual": float(actual),
                "prediction": predicted,
                "error": error,
                "abs_error": abs(error),
                "model_version": record.get("model_version"),
                "reconciled_at": utc_now_iso(),
            }
        )
        written += 1

    _rewrite_pending_predictions(remaining)
    summary_path = MONITORING_DIR / "reconcile_summary.json"
    summary = {
        "dataset": str(path),
        "matched": matched,
        "written": written,
        "pending_remaining": len(remaining),
        "at": utc_now_iso(),
    }
    write_json(summary_path, summary)
    return summary


def evaluate_holdout_accuracy(target: str, days: int = 14) -> dict[str, object]:
    """Compare active-model predictions to recent actuals (offline sanity check)."""
    normalized_path = _latest_usable_normalized_path()
    if normalized_path is None:
        raise ValueError("No normalized dataset found.")

    df = pd.read_csv(normalized_path).sort_values("date").reset_index(drop=True)
    if target not in df.columns:
        raise ValueError(f"Target '{target}' not found.")

    series = pd.to_numeric(df[target], errors="coerce")
    observed = df[series.notna()].tail(days)
    if observed.empty:
        raise ValueError(f"No recent actuals for target '{target}'.")

    model_entry = get_current_model(target)
    errors: list[float] = []
    for _, row in observed.iterrows():
        date = str(row["date"])
        try:
            result = predict_for_date(target, date)
        except ValueError:
            continue
        actual = float(row[target])
        errors.append(abs(actual - float(result["prediction"])))

    if not errors:
        raise ValueError(f"Could not evaluate holdout accuracy for '{target}'.")

    return {
        "target": target,
        "days_evaluated": len(errors),
        "mae": round(float(sum(errors) / len(errors)), 6),
        "model_version": model_entry["model_version"],
        "evaluated_at": utc_now_iso(),
    }


def _load_pending_predictions() -> list[dict[str, object]]:
    if not PREDICTIONS_LOG.exists():
        return []
    records: list[dict[str, object]] = []
    with PREDICTIONS_LOG.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _rewrite_pending_predictions(records: list[dict[str, object]]) -> None:
    MONITORING_DIR.mkdir(parents=True, exist_ok=True)
    with PREDICTIONS_LOG.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _append_accuracy(record: dict[str, object]) -> None:
    MONITORING_DIR.mkdir(parents=True, exist_ok=True)
    with ERRORS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def accuracy_summary() -> dict[str, object]:
    if not ERRORS_LOG.exists():
        return {"targets": {}, "total_records": 0}

    by_target: dict[str, list[float]] = {}
    total = 0
    with ERRORS_LOG.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            target = str(payload["target"])
            by_target.setdefault(target, []).append(float(payload["abs_error"]))
            total += 1

    targets_summary = {
        target: {
            "count": len(errors),
            "mae": round(sum(errors) / len(errors), 4),
        }
        for target, errors in by_target.items()
    }
    return {"targets": targets_summary, "total_records": total}


def registry_summary() -> dict[str, object]:
    if not MODEL_REGISTRY_PATH.exists():
        return {"active_models": 0, "publishable_with_active": 0}
    payload = read_json(MODEL_REGISTRY_PATH)
    models = payload.get("models", {})
    active = sum(1 for entries in models.values() for entry in entries if entry.get("active"))
    adopted_versions = sum(
        1 for entries in models.values() for entry in entries if entry.get("evaluation", {}).get("adopted")
    )
    return {
        "active_models": active,
        "targets_with_registry": len(models),
        "adopted_versions_total": adopted_versions,
    }
