from fastapi import APIRouter, HTTPException, status
from pymongo.errors import PyMongoError

from ..schemas.predict import PredictRequest, PredictResponse
from ..services.ml_service import (
    InferenceError,
    ModelNotFoundError,
    NoModelsLoadedError,
    ml_service,
)
from ..database.mongo import get_database
from ..models.prediction import PredictionDocument

router = APIRouter(tags=["predict"])


@router.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    try:
        out = ml_service.predict(req.text, req.model)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except NoModelsLoadedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except InferenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    prediction = PredictionDocument(
        text=req.text,
        prediction=out["prediction"],
        confidence=out.get("confidence"),
        probabilities=out.get("probabilities", {}),
        model=out.get("model"),
    )
    history_saved = True
    try:
        db = get_database()
        await db.predictions.insert_one(prediction.model_dump())
    except (RuntimeError, PyMongoError):
        history_saved = False

    return {
        "prediction": out["prediction"],
        "confidence": out.get("confidence"),
        "probabilities": out.get("probabilities", {}),
        "model": out["model"],
        "history_saved": history_saved,
    }
