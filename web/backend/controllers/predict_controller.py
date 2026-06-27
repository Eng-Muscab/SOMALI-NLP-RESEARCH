from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.errors import PyMongoError

from ..database.mongo import get_database
from ..models.prediction import PredictionDocument
from ..schemas.predict import PredictRequest, PredictResponse
from ..services.activity_service import log_activity
from ..services.ml_service import (
    InferenceError,
    ModelNotFoundError,
    NoModelsLoadedError,
    ml_service,
)
from ..services.category_service import category_service
from ..utils.dependencies import get_current_user

router = APIRouter(tags=["predict"])


async def _check_and_increment_quota(user_id: str, db) -> None:
    from bson import ObjectId

    if not user_id or not ObjectId.is_valid(user_id):
        return

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return

    daily_limit: int = user.get("daily_prediction_limit", 20)
    monthly_limit: int = user.get("monthly_prediction_limit", 200)

    # Unlimited (-1) — skip quota checks
    if daily_limit == -1 and monthly_limit == -1:
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"daily_prediction_count": 1, "monthly_prediction_count": 1}},
        )
        return

    today_str = date.today().isoformat()
    month_str = datetime.now(timezone.utc).strftime("%Y-%m")

    # Reset daily counter if day changed
    reset: dict = {}
    if user.get("last_count_reset") != today_str:
        reset["daily_prediction_count"] = 0
        reset["last_count_reset"] = today_str
    if user.get("last_month_reset") != month_str:
        reset["monthly_prediction_count"] = 0
        reset["last_month_reset"] = month_str
    if reset:
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": reset})
        user.update(reset)

    daily_used = user.get("daily_prediction_count", 0)
    monthly_used = user.get("monthly_prediction_count", 0)

    if daily_limit != -1 and daily_used >= daily_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily prediction limit reached ({daily_limit}/day). Upgrade your plan.",
        )
    if monthly_limit != -1 and monthly_used >= monthly_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly prediction limit reached ({monthly_limit}/month). Upgrade your plan.",
        )

    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$inc": {"daily_prediction_count": 1, "monthly_prediction_count": 1}},
    )


@router.post("/predict", response_model=PredictResponse)
async def predict(
    req: PredictRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()

    # Enforce quota
    await _check_and_increment_quota(current_user.get("id", ""), db)

    # Enforce text length limit
    max_len: int = current_user.get("max_text_length", 5000) or 5000
    if len(req.text) > max_len:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Text exceeds the {max_len}-character limit for your plan.",
        )

    try:
        out = ml_service.predict(req.text, req.model)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except NoModelsLoadedError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except InferenceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    cat_result = category_service.predict(req.text)

    prediction = PredictionDocument(
        text=req.text,
        prediction=out["prediction"],
        confidence=out.get("confidence"),
        probabilities=out.get("probabilities", {}),
        model=out.get("model"),
    )
    history_saved = True
    try:
        await db.predictions.insert_one(prediction.model_dump())
    except (RuntimeError, PyMongoError):
        history_saved = False

    # Async audit log (fire-and-forget style via try/except)
    try:
        await log_activity(
            user_id=current_user.get("id", ""),
            user_email=current_user.get("email", ""),
            user_name=current_user.get("name", ""),
            action="prediction_made",
            category="prediction",
            details={
                "model": out.get("model"),
                "prediction": out["prediction"],
                "confidence": round(out.get("confidence", 0) * 100, 1),
                "text_length": len(req.text),
            },
        )
    except Exception:
        pass

    return {
        "prediction": out["prediction"],
        "label": out["prediction"],
        "score": out.get("confidence"),
        "confidence": out.get("confidence"),
        "probabilities": out.get("probabilities", {}),
        "model": out["model"],
        "history_saved": history_saved,
        "category": cat_result["category"],
        "category_icon": cat_result["icon"],
    }
