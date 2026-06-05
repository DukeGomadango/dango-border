from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status

from app.core.availability import get_prediction_date_range
from app.core.preprocess import normalize_raw_dataset
from app.core.quality import evaluate_quality_gate
from app.core.settings import ALLOWED_EXTENSIONS, JOBS_DIR, MAX_UPLOAD_SIZE_BYTES, STORAGE_DIR, UPLOADS_DIR
from app.core.storage import append_audit_log, read_json, utc_now_iso, write_json
from app.core.monitoring import reconcile_prediction_accuracy
from app.core.targets import TARGETS_PATH, rebuild_targets_registry
from app.core.targets_ops import list_targets_with_operations
from app.models.schemas import (
    JobStatusResponse,
    PredictionDateRangeResponse,
    QualityGateOverrideRequest,
    TargetOperationsInfo,
    TargetOperationsResponse,
    TargetPublishUpdateRequest,
    TargetsResponse,
    UploadResponse,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


async def _save_upload_file(upload_file: UploadFile, destination: Path) -> int:
    total_size = 0
    with destination.open("wb") as f:
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Max size is {MAX_UPLOAD_SIZE_BYTES} bytes.",
                )
            f.write(chunk)
    return total_size


def _simulate_pipeline(job_id: str) -> None:
    job_file = _job_path(job_id)
    job = read_json(job_file)
    try:
        job["status"] = "running"
        job["stage"] = "normalizing"
        job["updated_at"] = utc_now_iso()
        write_json(job_file, job)

        dataset_path = Path(job["dataset_path"])
        normalized_path = JOBS_DIR / f"{job_id}_normalized.csv"
        result = normalize_raw_dataset(dataset_path, normalized_path)
        from app.core.r2 import upload_to_r2
        upload_to_r2(normalized_path)
        target_update = rebuild_targets_registry(normalized_path)
        baseline_path = _latest_completed_normalized_path(exclude_job_id=job_id)
        quality_result = evaluate_quality_gate(normalized_path, baseline_path=baseline_path)

        job["status"] = "completed"
        job["stage"] = "quality_gate_passed" if quality_result.passed else "quality_gate_failed"
        job["normalized_dataset_path"] = str(result.output_path)
        job["pipeline_blocked"] = quality_result.pipeline_blocked
        job["quality_gate"] = {
            "passed": quality_result.passed,
            "metrics": quality_result.metrics,
            "reasons": quality_result.reasons,
            "thresholds": {
                "missing_rate_max": 0.55,
                "duplicate_rate_max": 0.02,
                "row_count_drop_max": 0.30,
                "psi_mean_max": 0.25,
            },
        }
        job["summary"] = {
            "rows_total": result.rows_total,
            "rows_data": result.rows_data,
            "month_headers": result.month_headers,
            "dropped_rows": result.dropped_rows,
            "targets_total": target_update.targets_total,
            "targets_ready": target_update.ready_count,
            "targets_beta": target_update.beta_count,
            "targets_blocked": target_update.blocked_count,
        }
        job["updated_at"] = utc_now_iso()
        write_json(job_file, job)

        reconcile_summary = reconcile_prediction_accuracy(normalized_path)

        append_audit_log(
            {
                "event": "dataset_normalized",
                "job_id": job_id,
                "normalized_dataset_path": str(result.output_path),
                "monitoring_reconcile": reconcile_summary,
                "rows_total": result.rows_total,
                "rows_data": result.rows_data,
                "month_headers": result.month_headers,
                "dropped_rows": result.dropped_rows,
                "quality_gate": job["quality_gate"],
                "pipeline_blocked": quality_result.pipeline_blocked,
                "targets_registry_path": str(target_update.targets_path),
                "at": utc_now_iso(),
            }
        )
    except Exception as exc:
        job["status"] = "failed"
        job["stage"] = "failed"
        job["error"] = str(exc)
        job["updated_at"] = utc_now_iso()
        write_json(job_file, job)

        append_audit_log(
            {
                "event": "dataset_normalize_failed",
                "job_id": job_id,
                "error": str(exc),
                "at": utc_now_iso(),
            }
        )


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_dataset(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> UploadResponse:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{extension}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    job_id = str(uuid4())
    stored_name = f"{job_id}{extension}"
    destination = UPLOADS_DIR / stored_name

    try:
        size = await _save_upload_file(file, destination)
    finally:
        await file.close()

    from app.core.r2 import upload_to_r2
    upload_to_r2(destination)

    now = utc_now_iso()
    job = {
        "job_id": job_id,
        "status": "queued",
        "stage": "uploaded",
        "created_at": now,
        "updated_at": now,
        "dataset_path": str(destination),
        "original_filename": filename,
        "size_bytes": size,
        "error": None,
    }
    write_json(_job_path(job_id), job)

    append_audit_log(
        {
            "event": "dataset_uploaded",
            "job_id": job_id,
            "filename": filename,
            "stored_path": str(destination),
            "size_bytes": size,
            "at": now,
        }
    )

    background_tasks.add_task(_simulate_pipeline, job_id)
    return UploadResponse(job_id=job_id, status="queued", message="Upload accepted and job queued.")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    job_file = _job_path(job_id)
    if not job_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    payload = read_json(job_file)
    return JobStatusResponse(
        job_id=payload["job_id"],
        status=payload["status"],
        stage=payload["stage"],
        created_at=datetime.fromisoformat(payload["created_at"]).astimezone(UTC),
        updated_at=datetime.fromisoformat(payload["updated_at"]).astimezone(UTC),
        dataset_path=payload["dataset_path"],
        error=payload.get("error"),
        pipeline_blocked=bool(payload.get("pipeline_blocked", False)),
        quality_gate=payload.get("quality_gate"),
        summary=payload.get("summary"),
    )


@router.post("/jobs/{job_id}/quality-gate/override", response_model=JobStatusResponse)
def override_quality_gate(job_id: str, request: QualityGateOverrideRequest) -> JobStatusResponse:
    job_file = _job_path(job_id)
    if not job_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    payload = read_json(job_file)
    if "quality_gate" not in payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quality gate has not been evaluated yet.")

    payload["pipeline_blocked"] = False
    payload["stage"] = "quality_gate_overridden"
    payload["quality_gate"]["manual_override"] = True
    payload["quality_gate"]["override_reason"] = request.reason
    payload["quality_gate"]["override_at"] = utc_now_iso()
    payload["updated_at"] = utc_now_iso()
    write_json(job_file, payload)

    append_audit_log(
        {
            "event": "quality_gate_overridden",
            "job_id": job_id,
            "reason": request.reason,
            "at": utc_now_iso(),
        }
    )

    return JobStatusResponse(
        job_id=payload["job_id"],
        status=payload["status"],
        stage=payload["stage"],
        created_at=datetime.fromisoformat(payload["created_at"]).astimezone(UTC),
        updated_at=datetime.fromisoformat(payload["updated_at"]).astimezone(UTC),
        dataset_path=payload["dataset_path"],
        error=payload.get("error"),
        pipeline_blocked=bool(payload.get("pipeline_blocked", False)),
        quality_gate=payload.get("quality_gate"),
        summary=payload.get("summary"),
    )


@router.get("/targets", response_model=TargetsResponse)
def get_targets() -> TargetsResponse:
    if not TARGETS_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Targets registry not found. Upload and process a dataset first.",
        )

    payload = read_json(TARGETS_PATH)
    return TargetsResponse(
        updated_at=datetime.fromisoformat(payload["updated_at"]).astimezone(UTC),
        source_dataset=payload.get("source_dataset", str(STORAGE_DIR)),
        summary=payload.get("summary", {}),
        targets=payload.get("targets", []),
    )


@router.get("/targets/operations", response_model=TargetOperationsResponse)
def targets_operations() -> TargetOperationsResponse:
    if not TARGETS_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Targets registry not found. Upload and process a dataset first.",
        )
    rows = list_targets_with_operations()
    return TargetOperationsResponse(updated_at=utc_now_iso(), targets=[TargetOperationsInfo(**row) for row in rows])


@router.get("/targets/{target}/prediction-range", response_model=PredictionDateRangeResponse)
def target_prediction_range(target: str) -> PredictionDateRangeResponse:
    try:
        result = get_prediction_date_range(target)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return PredictionDateRangeResponse(
        target=result.target,
        min_date=result.min_date,
        max_date=result.max_date,
        predict_to=result.predict_to,
        rows_available=result.rows_available,
        has_active_model=result.has_active_model,
    )


@router.patch("/targets/{target}/publish", response_model=TargetsResponse)
def update_target_publish(target: str, request: TargetPublishUpdateRequest) -> TargetsResponse:
    if not TARGETS_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Targets registry not found. Upload and process a dataset first.",
        )

    payload = read_json(TARGETS_PATH)
    targets = payload.get("targets", [])

    found = False
    for item in targets:
        if item.get("target") != target:
            continue

        found = True
        current_status = item.get("status")
        if current_status == "blocked" and request.publish:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Blocked target cannot be published.",
            )
        item["publish"] = request.publish
        item["updated_at"] = utc_now_iso()
        break

    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    payload["updated_at"] = utc_now_iso()
    payload["targets"] = targets
    write_json(TARGETS_PATH, payload)

    append_audit_log(
        {
            "event": "target_publish_updated",
            "target": target,
            "publish": request.publish,
            "reason": request.reason,
            "at": utc_now_iso(),
        }
    )

    return TargetsResponse(
        updated_at=datetime.fromisoformat(payload["updated_at"]).astimezone(UTC),
        source_dataset=payload.get("source_dataset", str(STORAGE_DIR)),
        summary=payload.get("summary", {}),
        targets=payload.get("targets", []),
    )


def _latest_completed_normalized_path(exclude_job_id: str) -> Path | None:
    latest_path: Path | None = None
    latest_updated: datetime | None = None
    for job_file in JOBS_DIR.glob("*.json"):
        payload = read_json(job_file)
        if payload.get("job_id") == exclude_job_id:
            continue
        normalized_path = payload.get("normalized_dataset_path")
        if not normalized_path:
            continue
        if payload.get("status") != "completed":
            continue
        updated_raw = payload.get("updated_at")
        if not updated_raw:
            continue
        updated_at = datetime.fromisoformat(updated_raw)
        if latest_updated is None or updated_at > latest_updated:
            candidate = Path(normalized_path)
            if candidate.exists():
                latest_updated = updated_at
                latest_path = candidate
    return latest_path

