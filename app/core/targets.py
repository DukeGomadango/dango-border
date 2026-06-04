from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.settings import STORAGE_DIR
from app.core.storage import read_json, utc_now_iso, write_json


TARGETS_PATH = STORAGE_DIR / "targets.json"

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


@dataclass
class TargetsUpdateResult:
    targets_total: int
    ready_count: int
    beta_count: int
    blocked_count: int
    targets_path: Path


def rebuild_targets_registry(normalized_path: Path) -> TargetsUpdateResult:
    df = pd.read_csv(normalized_path)
    if df.empty:
        raise ValueError("Normalized dataset is empty. Cannot rebuild targets.")

    feature_cols = [col for col in df.columns if col not in META_COLUMNS]
    if not feature_cols:
        raise ValueError("No feature columns found in normalized dataset.")

    total_rows = len(df)
    rows: list[dict[str, object]] = []
    ready = 0
    beta = 0
    blocked = 0
    now = utc_now_iso()

    existing_publish_map = _load_publish_map()

    for target in feature_cols:
        values = pd.to_numeric(df[target], errors="coerce")
        valid_count = int(values.notna().sum())
        coverage = float(valid_count / total_rows) if total_rows else 0.0
        missing_rate = 1.0 - coverage
        unique_values = int(values.nunique(dropna=True))

        status = _decide_status(valid_count=valid_count, coverage=coverage)
        if status == "ready":
            ready += 1
        elif status == "beta":
            beta += 1
        else:
            blocked += 1

        default_publish = status == "ready"
        publish = existing_publish_map.get(target, default_publish)
        if status == "blocked":
            publish = False

        rows.append(
            {
                "target": target,
                "valid_count": valid_count,
                "coverage": round(coverage, 6),
                "missing_rate": round(missing_rate, 6),
                "unique_values": unique_values,
                "status": status,
                "publish": publish,
                "updated_at": now,
            }
        )

    payload = {
        "updated_at": now,
        "source_dataset": str(normalized_path),
        "summary": {
            "targets_total": len(rows),
            "ready_count": ready,
            "beta_count": beta,
            "blocked_count": blocked,
            "rows_total": total_rows,
        },
        "targets": sorted(rows, key=lambda x: (x["status"], -float(x["coverage"]))),
    }
    write_json(TARGETS_PATH, payload)

    return TargetsUpdateResult(
        targets_total=len(rows),
        ready_count=ready,
        beta_count=beta,
        blocked_count=blocked,
        targets_path=TARGETS_PATH,
    )


def _decide_status(valid_count: int, coverage: float) -> str:
    if valid_count >= 500 and coverage >= 0.50:
        return "ready"
    if valid_count >= 300 and coverage >= 0.30:
        return "beta"
    return "blocked"


def _load_publish_map() -> dict[str, bool]:
    if not TARGETS_PATH.exists():
        return {}
    payload = read_json(TARGETS_PATH)
    targets = payload.get("targets", [])
    result: dict[str, bool] = {}
    for target in targets:
        name = target.get("target")
        publish = target.get("publish")
        if isinstance(name, str) and isinstance(publish, bool):
            result[name] = publish
    return result

