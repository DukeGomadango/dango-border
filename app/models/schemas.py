from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class UploadResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: str
    created_at: datetime
    updated_at: datetime
    dataset_path: str
    error: str | None = None
    pipeline_blocked: bool = False
    quality_gate: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None


class QualityGateOverrideRequest(BaseModel):
    reason: str


class TargetInfo(BaseModel):
    target: str
    valid_count: int
    coverage: float
    missing_rate: float
    unique_values: int
    status: Literal["ready", "beta", "blocked"]
    publish: bool
    updated_at: datetime


class TargetsResponse(BaseModel):
    updated_at: datetime
    source_dataset: str
    summary: dict[str, int]
    targets: list[TargetInfo]


class TargetPublishUpdateRequest(BaseModel):
    publish: bool
    reason: str


class PredictionDateRangeResponse(BaseModel):
    target: str
    min_date: str
    max_date: str
    predict_to: str
    rows_available: int
    has_active_model: bool


class TargetOperationsInfo(BaseModel):
    target: str
    status: str
    publish: bool
    coverage: float
    missing_rate: float
    valid_count: int
    has_active_model: bool
    active_model_version: str | None = None
    active_model_type: str | None = None
    last_trained_at: str | None = None
    last_adopted: bool = False
    cv_mae: float | None = None
    baseline_mae: float | None = None
    improvement_rate: float | None = None


class TargetOperationsResponse(BaseModel):
    updated_at: str
    targets: list[TargetOperationsInfo]


class SystemMetricsResponse(BaseModel):
    counters: dict[str, int | str]
    accuracy: dict[str, object]
    registry: dict[str, object]
    generated_at: str


class AuditLogResponse(BaseModel):
    lines: list[dict[str, object]]
    count: int


class PublicationPlanResponse(BaseModel):
    goal: int
    published_count: int
    remaining_slots: int
    ready_published: int
    beta_published: int
    beta_candidates_eligible: int
    beta_candidates_total: int
    updated_at: str


class PublicationCandidateInfo(BaseModel):
    target: str
    status: str
    publish: bool
    eligible: bool
    reasons: list[str]
    has_active_model: bool
    adopted: bool
    improvement_rate: float | None = None
    cv_mae: float | None = None


class PublicationCandidatesResponse(BaseModel):
    candidates: list[PublicationCandidateInfo]


class PromoteTargetRequest(BaseModel):
    target: str
    reason: str
    force: bool = False


class PromoteTargetResponse(BaseModel):
    target: str
    promoted: bool
    message: str
    plan: PublicationPlanResponse


class PromoteBatchRequest(BaseModel):
    limit: int | None = None
    reason: str = "beta quality gate passed"


class PromoteBatchResponse(BaseModel):
    goal: int
    promoted: list[str]
    skipped: list[dict[str, str]]
    promoted_count: int
    plan: PublicationPlanResponse
    at: str



class TrainResponse(BaseModel):
    target: str
    model_version: str
    model_type: str
    feature_profile: str
    artifact_path: str
    rows_train: int
    metrics: dict[str, float]
    adopted: bool
    improvement_rate: float
    cv_mae: float
    baseline_mae: float


class TrainAllResponse(BaseModel):
    results: list[dict[str, Any]]
    errors: list[dict[str, str]]


class CurrentModelResponse(BaseModel):
    target: str
    model_version: str
    artifact_path: str
    metrics: dict[str, float]
    active: bool
    created_at: str
    evaluation: dict[str, Any] | None = None


class ModelVersionInfo(BaseModel):
    target: str
    model_version: str
    artifact_path: str
    metrics: dict[str, float]
    active: bool
    created_at: str
    evaluation: dict[str, Any] | None = None


class ModelVersionsResponse(BaseModel):
    target: str
    versions: list[ModelVersionInfo]


class ActivateModelRequest(BaseModel):
    model_version: str
    reason: str


class PredictionInterval(BaseModel):
    p10: float
    p50: float
    p90: float


class PredictionResponse(BaseModel):
    target: str
    date: str
    prediction: float
    interval: PredictionInterval
    model_version: str
    model_type: str
    quality_status: str
    trained_at: str | None = None


class PredictionRangeResponse(BaseModel):
    target: str
    from_date: str
    to_date: str
    model_version: str
    model_type: str
    count: int
    predictions: list[PredictionResponse]
    errors: list[dict[str, str]]


# ---------------------------------------------------------------------------
# Deep Learning Prediction Schemas
# ---------------------------------------------------------------------------

class DeepTierPrediction(BaseModel):
    """Quantile predictions for a single tier (e.g., S1 +2)."""

    p10: float
    p50: float
    p90: float


class DeepStepPrediction(BaseModel):
    """Predictions for all tiers at a single future date."""

    date: str
    event_day: int
    predictions: dict[str, DeepTierPrediction]


class DeepGroupForecastResponse(BaseModel):
    """Multi-step forecast for a target group (e.g., S1 → S1+2, S1+4, S1+6)."""

    target_group: str
    from_date: str
    to_date: str
    model_version: str
    model_type: str
    count: int
    steps: list[DeepStepPrediction]
    blending_status: str | None = None
    w_tft: float | None = None


class DeepTrainResponse(BaseModel):
    """Response from training a deep learning model."""

    target_group: str
    tier_columns: list[str]
    model_version: str
    model_path: str
    train_loss: float
    val_loss: float
    epochs_trained: int


