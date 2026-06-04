from fastapi import APIRouter, HTTPException, status

from app.core.inference import predict_for_date, predict_for_date_range
from app.core.metrics import record_prediction_served
from app.core.monitoring import log_prediction_served
from app.core.storage import append_audit_log, utc_now_iso
from app.models.schemas import PredictionRangeResponse, PredictionResponse

router = APIRouter(tags=["predictions"])


def _http_code_for_prediction_error(detail: str) -> int:
    if "not published" in detail or "blocked" in detail:
        return status.HTTP_403_FORBIDDEN
    if "No active model" in detail:
        return status.HTTP_404_NOT_FOUND
    return status.HTTP_400_BAD_REQUEST


@router.get("/predictions", response_model=PredictionResponse)
def get_prediction(target: str, date: str) -> PredictionResponse:
    try:
        result = predict_for_date(target=target, date=date)
    except ValueError as exc:
        raise HTTPException(status_code=_http_code_for_prediction_error(str(exc)), detail=str(exc)) from exc

    record_prediction_served()
    log_prediction_served(
        target=target,
        date=date,
        prediction=float(result["prediction"]),
        model_version=str(result["model_version"]),
        model_type=str(result["model_type"]),
    )
    append_audit_log(
        {
            "event": "prediction_served",
            "target": target,
            "date": date,
            "model_version": result["model_version"],
            "prediction": result["prediction"],
            "at": utc_now_iso(),
        }
    )
    return PredictionResponse(**result)


@router.get("/predictions/range", response_model=PredictionRangeResponse)
def get_prediction_range(target: str, from_date: str, to_date: str) -> PredictionRangeResponse:
    try:
        result = predict_for_date_range(target=target, from_date=from_date, to_date=to_date)
    except ValueError as exc:
        raise HTTPException(status_code=_http_code_for_prediction_error(str(exc)), detail=str(exc)) from exc

    for item in result["predictions"]:
        record_prediction_served()
        log_prediction_served(
            target=target,
            date=str(item["date"]),
            prediction=float(item["prediction"]),
            model_version=str(item["model_version"]),
            model_type=str(item["model_type"]),
        )

    append_audit_log(
        {
            "event": "prediction_range_served",
            "target": target,
            "from_date": from_date,
            "to_date": to_date,
            "count": result["count"],
            "at": utc_now_iso(),
        }
    )
    return PredictionRangeResponse(
        target=result["target"],
        from_date=result["from_date"],
        to_date=result["to_date"],
        model_version=result["model_version"],
        model_type=result["model_type"],
        count=result["count"],
        predictions=[PredictionResponse(**item) for item in result["predictions"]],
        errors=result["errors"],
    )
