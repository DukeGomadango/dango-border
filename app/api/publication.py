from fastapi import APIRouter, HTTPException, status

from app.core.metrics import record_train_request
from app.core.publication import (
    evaluate_publication_eligibility,
    get_publication_plan,
    list_publication_candidates,
    promote_eligible_beta,
    promote_target,
    train_beta_candidates,
)
from app.core.storage import append_audit_log, utc_now_iso
from app.models.schemas import (
    PromoteBatchRequest,
    PromoteBatchResponse,
    PromoteTargetRequest,
    PromoteTargetResponse,
    PublicationCandidatesResponse,
    PublicationCandidateInfo,
    PublicationPlanResponse,
    TrainAllResponse,
)

router = APIRouter(prefix="/datasets/publication", tags=["publication"])


@router.get("/plan", response_model=PublicationPlanResponse)
def publication_plan() -> PublicationPlanResponse:
    return PublicationPlanResponse(**get_publication_plan())


@router.get("/candidates", response_model=PublicationCandidatesResponse)
def publication_candidates() -> PublicationCandidatesResponse:
    items = list_publication_candidates()
    return PublicationCandidatesResponse(
        candidates=[PublicationCandidateInfo(**item.__dict__) for item in items]
    )


@router.get("/candidates/{target}", response_model=PublicationCandidateInfo)
def publication_candidate(target: str) -> PublicationCandidateInfo:
    try:
        item = evaluate_publication_eligibility(target)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PublicationCandidateInfo(**item.__dict__)


@router.post("/promote", response_model=PromoteTargetResponse)
def promote_single(request: PromoteTargetRequest) -> PromoteTargetResponse:
    try:
        result = promote_target(request.target, reason=request.reason, force=request.force)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if result.promoted:
        append_audit_log(
            {
                "event": "target_promoted",
                "target": request.target,
                "reason": request.reason,
                "force": request.force,
                "at": utc_now_iso(),
            }
        )

    return PromoteTargetResponse(
        target=result.target,
        promoted=result.promoted,
        message=result.message,
        plan=PublicationPlanResponse(**get_publication_plan()),
    )


@router.post("/promote-batch", response_model=PromoteBatchResponse)
def promote_batch(request: PromoteBatchRequest) -> PromoteBatchResponse:
    output = promote_eligible_beta(limit=request.limit, reason=request.reason)
    if output["promoted"]:
        append_audit_log(
            {
                "event": "targets_promoted_batch",
                "promoted": output["promoted"],
                "reason": request.reason,
                "at": utc_now_iso(),
            }
        )
    return PromoteBatchResponse(
        goal=int(output["goal"]),
        promoted=list(output["promoted"]),
        skipped=list(output["skipped"]),
        promoted_count=int(output["promoted_count"]),
        plan=PublicationPlanResponse(**output["plan"]),
        at=str(output["at"]),
    )


@router.post("/train-beta", response_model=TrainAllResponse)
def train_beta() -> TrainAllResponse:
    output = train_beta_candidates()
    for _item in output["results"]:
        record_train_request(success=True)
    for _item in output["errors"]:
        record_train_request(success=False)
    append_audit_log(
        {
            "event": "beta_candidates_trained",
            "success_count": len(output["results"]),
            "error_count": len(output["errors"]),
            "at": utc_now_iso(),
        }
    )
    return TrainAllResponse(results=output["results"], errors=output["errors"])
