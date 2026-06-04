import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.settings import AUDIT_DIR, JOBS_DIR, MODELS_DIR, MONITORING_DIR, STORAGE_DIR, UPLOADS_DIR


def ensure_storage_dirs() -> None:
    for directory in (STORAGE_DIR, UPLOADS_DIR, JOBS_DIR, AUDIT_DIR, MODELS_DIR, MONITORING_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def append_audit_log(event: dict[str, Any]) -> None:
    log_path = AUDIT_DIR / "audit.log"
    line = json.dumps(event, ensure_ascii=False)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

