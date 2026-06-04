"""API endpoints for deep learning model training and multi-step predictions."""
from fastapi import APIRouter, HTTPException, status

from app.core.deep_inference import predict_group_future
from app.core.deep_training import train_deep_model
from app.core.hybrid_inference import predict_hybrid
from app.core.model_cache import reload_model
from app.core.storage import append_audit_log, utc_now_iso
from app.models.schemas import (
    DeepGroupForecastResponse,
    DeepStepPrediction,
    DeepTierPrediction,
    DeepTrainResponse,
)

router = APIRouter(prefix="/deep", tags=["deep-learning"])


@router.post("/train", response_model=DeepTrainResponse)
def deep_train(
    target_group: str,
    encoder_len: int = 90,
    decoder_len: int = 7,
    epochs: int = 100,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    patience: int = 10,
) -> DeepTrainResponse:
    """Train a deep learning model for a target group (e.g., 'S1')."""
    try:
        result = train_deep_model(
            target_group=target_group,
            encoder_len=encoder_len,
            decoder_len=decoder_len,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            patience=patience,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    append_audit_log({
        "event": "deep_model_trained",
        "target_group": target_group,
        "model_version": result.model_version,
        "train_loss": result.train_loss,
        "val_loss": result.val_loss,
        "epochs_trained": result.epochs_trained,
        "at": utc_now_iso(),
    })

    # Refresh the in-memory cache so the next prediction request uses the
    # newly trained weights without requiring a server restart.
    try:
        reload_model(target_group)
    except Exception:
        pass  # Non-fatal: cache will be stale until next restart

    return DeepTrainResponse(
        target_group=result.target_group,
        tier_columns=result.tier_columns,
        model_version=result.model_version,
        model_path=result.model_path,
        train_loss=result.train_loss,
        val_loss=result.val_loss,
        epochs_trained=result.epochs_trained,
    )


@router.get("/predictions", response_model=DeepGroupForecastResponse)
def deep_predict(
    target_group: str,
    from_date: str,
    to_date: str,
    use_hybrid: bool = True,
    w_tft: float = 0.6,
) -> DeepGroupForecastResponse:
    """Get multi-step predictions for a target group with guaranteed tier ordering."""
    try:
        if use_hybrid:
            result = predict_hybrid(
                target_group=target_group,
                from_date=from_date,
                to_date=to_date,
                w_tft=w_tft,
            )
        else:
            result = predict_group_future(
                target_group=target_group,
                from_date=from_date,
                to_date=to_date,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    append_audit_log({
        "event": "deep_prediction_served",
        "target_group": target_group,
        "from_date": from_date,
        "to_date": to_date,
        "use_hybrid": use_hybrid,
        "w_tft": w_tft,
        "blending_status": result.get("blending_status"),
        "model_version": result["model_version"],
        "count": result["count"],
        "at": utc_now_iso(),
    })

    steps = []
    for step in result["steps"]:
        tier_preds = {}
        for tier_name, vals in step["predictions"].items():
            tier_preds[tier_name] = DeepTierPrediction(**vals)
        steps.append(DeepStepPrediction(
            date=step["date"],
            event_day=step["event_day"],
            predictions=tier_preds,
        ))

    return DeepGroupForecastResponse(
        target_group=result["target_group"],
        from_date=result["from_date"],
        to_date=result["to_date"],
        model_version=result["model_version"],
        model_type=result["model_type"],
        count=result["count"],
        steps=steps,
        blending_status=result.get("blending_status"),
        w_tft=result.get("w_tft"),
    )
