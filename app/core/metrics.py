from typing import Any

from app.core.monitoring import accuracy_summary, registry_summary
from app.core.settings import METRICS_PATH
from app.core.storage import read_json, utc_now_iso, write_json


def _default_metrics() -> dict[str, Any]:
    return {
        "predictions_served": 0,
        "prediction_errors": 0,
        "train_requests": 0,
        "train_success": 0,
        "train_failed": 0,
        "updated_at": utc_now_iso(),
    }


def load_metrics() -> dict[str, Any]:
    if not METRICS_PATH.exists():
        return _default_metrics()
    payload = read_json(METRICS_PATH)
    for key, value in _default_metrics().items():
        payload.setdefault(key, value)
    return payload


def increment(counter: str, amount: int = 1) -> None:
    payload = load_metrics()
    payload[counter] = int(payload.get(counter, 0)) + amount
    payload["updated_at"] = utc_now_iso()
    write_json(METRICS_PATH, payload)


def record_prediction_served() -> None:
    increment("predictions_served")


def record_train_request(success: bool) -> None:
    increment("train_requests")
    if success:
        increment("train_success")
    else:
        increment("train_failed")


def build_system_metrics() -> dict[str, Any]:
    counters = load_metrics()
    accuracy = accuracy_summary()
    registry = registry_summary()
    return {
        "counters": counters,
        "accuracy": accuracy,
        "registry": registry,
        "generated_at": utc_now_iso(),
    }
