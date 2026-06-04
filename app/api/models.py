from fastapi import APIRouter, HTTPException, status

from app.core.metrics import record_train_request
from app.core.storage import append_audit_log, utc_now_iso
from app.core.training import (
    activate_model_version,
    get_current_model,
    list_model_versions,
    rollback_model,
    train_all_publishable_targets,
    train_target_model,
)
from app.models.schemas import (
    ActivateModelRequest,
    CurrentModelResponse,
    ModelVersionInfo,
    ModelVersionsResponse,
    TrainAllResponse,
    TrainResponse,
)

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/train", response_model=TrainResponse)
def train_single_target(
    target: str,
    strategy: str = "auto",
    feature_profile: str = "auto_steps",
) -> TrainResponse:
    try:
        result = train_target_model(target, feature_profile=feature_profile, strategy=strategy)
    except ValueError as exc:
        record_train_request(success=False)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    record_train_request(success=True)
    append_audit_log(
        {
            "event": "model_trained",
            "target": result.target,
            "model_version": result.model_version,
            "artifact_path": str(result.artifact_path),
            "rows_train": result.rows_train,
            "metrics": result.metrics,
            "at": utc_now_iso(),
        }
    )
    return TrainResponse(
        target=result.target,
        model_version=result.model_version,
        model_type=result.model_type,
        feature_profile=result.feature_profile,
        artifact_path=str(result.artifact_path),
        rows_train=result.rows_train,
        metrics=result.metrics,
        adopted=result.adopted,
        improvement_rate=result.evaluation.improvement_rate,
        cv_mae=result.evaluation.cv_mae,
        baseline_mae=result.evaluation.baseline_mae,
    )


@router.post("/train-all", response_model=TrainAllResponse)
def train_all() -> TrainAllResponse:
    output = train_all_publishable_targets()
    for item in output["results"]:
        record_train_request(success=True)
    for _item in output["errors"]:
        record_train_request(success=False)
    append_audit_log(
        {
            "event": "model_train_all_finished",
            "success_count": len(output["results"]),
            "error_count": len(output["errors"]),
            "at": utc_now_iso(),
        }
    )
    return TrainAllResponse(results=output["results"], errors=output["errors"])


@router.get("/current", response_model=CurrentModelResponse)
def current_model(target: str) -> CurrentModelResponse:
    try:
        payload = get_current_model(target)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return CurrentModelResponse(
        target=payload["target"],
        model_version=payload["model_version"],
        artifact_path=payload["artifact_path"],
        metrics=payload["metrics"],
        active=bool(payload["active"]),
        created_at=payload["created_at"],
        evaluation=payload.get("evaluation"),
    )


@router.get("/versions", response_model=ModelVersionsResponse)
def model_versions(target: str) -> ModelVersionsResponse:
    try:
        versions = list_model_versions(target)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ModelVersionsResponse(
        target=target,
        versions=[ModelVersionInfo(**v) for v in versions],
    )


@router.post("/activate", response_model=CurrentModelResponse)
def activate_model(target: str, request: ActivateModelRequest) -> CurrentModelResponse:
    try:
        payload = activate_model_version(target, request.model_version)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    append_audit_log(
        {
            "event": "model_activated",
            "target": target,
            "model_version": request.model_version,
            "reason": request.reason,
            "at": utc_now_iso(),
        }
    )
    return CurrentModelResponse(
        target=payload["target"],
        model_version=payload["model_version"],
        artifact_path=payload["artifact_path"],
        metrics=payload["metrics"],
        active=bool(payload["active"]),
        created_at=payload["created_at"],
        evaluation=payload.get("evaluation"),
    )


@router.post("/rollback", response_model=CurrentModelResponse)
def rollback(target: str, reason: str = "manual rollback") -> CurrentModelResponse:
    try:
        payload = rollback_model(target)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    append_audit_log(
        {
            "event": "model_rollback",
            "target": target,
            "model_version": payload["model_version"],
            "reason": reason,
            "at": utc_now_iso(),
        }
    )
    return CurrentModelResponse(
        target=payload["target"],
        model_version=payload["model_version"],
        artifact_path=payload["artifact_path"],
        metrics=payload["metrics"],
        active=bool(payload["active"]),
        created_at=payload["created_at"],
        evaluation=payload.get("evaluation"),
    )

