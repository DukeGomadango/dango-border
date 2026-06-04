import json

from fastapi import APIRouter, HTTPException, status

from app.core.metrics import build_system_metrics
from app.core.monitoring import evaluate_holdout_accuracy, reconcile_prediction_accuracy
from app.core.settings import AUDIT_DIR
from app.models.schemas import AuditLogResponse, SystemMetricsResponse

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/metrics", response_model=SystemMetricsResponse)
def system_metrics() -> SystemMetricsResponse:
    payload = build_system_metrics()
    return SystemMetricsResponse(**payload)


@router.get("/audit", response_model=AuditLogResponse)
def read_audit_log(tail: int = 50) -> AuditLogResponse:
    log_path = AUDIT_DIR / "audit.log"
    if not log_path.exists():
        return AuditLogResponse(lines=[], count=0)

    lines_raw = log_path.read_text(encoding="utf-8").splitlines()
    tail = max(1, min(tail, 500))
    selected = lines_raw[-tail:]
    parsed: list[dict[str, object]] = []
    for line in selected:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            parsed.append({"raw": line})
    return AuditLogResponse(lines=parsed, count=len(parsed))


@router.post("/monitoring/reconcile")
def monitoring_reconcile() -> dict[str, object]:
    try:
        return reconcile_prediction_accuracy()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/monitoring/holdout")
def monitoring_holdout(target: str, days: int = 14) -> dict[str, object]:
    try:
        return evaluate_holdout_accuracy(target, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
