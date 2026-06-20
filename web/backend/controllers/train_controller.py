from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..services.ml_service import ml_service
from ..services.training_service import TrainingStatus, training_service

router = APIRouter(prefix="/train", tags=["train"])


class TrainTraditionalRequest(BaseModel):
    all_traditional: bool = Field(default=True)
    include_random_forest: bool = Field(default=False)
    include_xgboost: bool = Field(default=False)


@router.get("/status")
async def training_status():
    return training_service.get_status()


@router.post("/traditional")
async def train_traditional_models(body: TrainTraditionalRequest | None = None):
    options = body or TrainTraditionalRequest()
    if training_service.is_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Training is already running.",
        )
    return await training_service.start_traditional_training(
        all_traditional=options.all_traditional,
        include_random_forest=options.include_random_forest,
        include_xgboost=options.include_xgboost,
    )


@router.post("/reload-models")
async def reload_models_after_training():
    if training_service.is_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wait for training to finish before reloading models.",
        )
    ml_service.load_models()
    loaded = ml_service.list_models()
    if not loaded and training_service.job.status == TrainingStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No models loaded. Check training logs and try training again.",
        )
    return {
        "status": "ok",
        "models_loaded": len(loaded),
        "models": loaded,
        "load_errors": ml_service.load_errors,
    }
