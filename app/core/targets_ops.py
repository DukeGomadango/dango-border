from pathlib import Path

from app.core.storage import read_json, utc_now_iso
from app.core.targets import TARGETS_PATH
from app.core.training import MODEL_REGISTRY_PATH


def list_targets_with_operations() -> list[dict[str, object]]:
    if not TARGETS_PATH.exists():
        return []

    targets_payload = read_json(TARGETS_PATH)
    registry = read_json(MODEL_REGISTRY_PATH) if MODEL_REGISTRY_PATH.exists() else {"models": {}}
    models_by_target: dict[str, list[dict[str, object]]] = registry.get("models", {})

    rows: list[dict[str, object]] = []
    for item in targets_payload.get("targets", []):
        target = item["target"]
        versions = models_by_target.get(target, [])
        active = next((v for v in versions if v.get("active")), None)
        latest = versions[-1] if versions else None
        evaluation = (active or latest or {}).get("evaluation") or {}

        rows.append(
            {
                "target": target,
                "status": item.get("status"),
                "publish": bool(item.get("publish")),
                "coverage": item.get("coverage"),
                "missing_rate": item.get("missing_rate"),
                "valid_count": item.get("valid_count"),
                "has_active_model": active is not None,
                "active_model_version": active.get("model_version") if active else None,
                "active_model_type": active.get("model_type") if active else None,
                "last_trained_at": (latest or {}).get("created_at"),
                "last_adopted": bool(evaluation.get("adopted", False)),
                "cv_mae": evaluation.get("cv_mae"),
                "baseline_mae": evaluation.get("baseline_mae"),
                "improvement_rate": evaluation.get("improvement_rate"),
            }
        )
    return rows
