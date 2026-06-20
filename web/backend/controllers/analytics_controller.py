from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from ..database.mongo import get_database
from ..utils.dependencies import require_admin

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def get_overview(current_user: dict = Depends(require_admin)):
    db = get_database()

    total_predictions = await db.predictions.count_documents({})
    ai_predictions = await db.predictions.count_documents({"prediction": "AI"})
    human_predictions = await db.predictions.count_documents({"prediction": "HUMAN"})
    total_users = await db.users.count_documents({})
    active_users = await db.users.count_documents({"is_active": True})

    # Today's predictions
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_predictions = await db.predictions.count_documents({"created_at": {"$gte": today_start}})

    # This month
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_predictions = await db.predictions.count_documents({"created_at": {"$gte": month_start}})

    # Most used models (top 5)
    pipeline = [
        {"$group": {"_id": "$model", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    model_cursor = db.predictions.aggregate(pipeline)
    top_models = [{"model": d["_id"], "count": d["count"]} async for d in model_cursor]

    # Average confidence
    conf_pipeline = [{"$group": {"_id": None, "avg_confidence": {"$avg": "$confidence"}}}]
    conf_result = await db.predictions.aggregate(conf_pipeline).to_list(1)
    avg_confidence = round(conf_result[0]["avg_confidence"] * 100, 1) if conf_result else 0

    return {
        "total_predictions": total_predictions,
        "ai_predictions": ai_predictions,
        "human_predictions": human_predictions,
        "ai_detection_rate": round(ai_predictions / total_predictions * 100, 1) if total_predictions else 0,
        "human_detection_rate": round(human_predictions / total_predictions * 100, 1) if total_predictions else 0,
        "total_users": total_users,
        "active_users": active_users,
        "today_predictions": today_predictions,
        "month_predictions": month_predictions,
        "avg_confidence": avg_confidence,
        "top_models": top_models,
    }


@router.get("/trends")
async def get_trends(
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(require_admin),
):
    db = get_database()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                    "day": {"$dayOfMonth": "$created_at"},
                },
                "total": {"$sum": 1},
                "ai": {"$sum": {"$cond": [{"$eq": ["$prediction", "AI"]}, 1, 0]}},
                "human": {"$sum": {"$cond": [{"$eq": ["$prediction", "HUMAN"]}, 1, 0]}},
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}},
    ]
    cursor = db.predictions.aggregate(pipeline)
    daily = [
        {
            "date": f"{d['_id']['year']}-{d['_id']['month']:02d}-{d['_id']['day']:02d}",
            "total": d["total"],
            "ai": d["ai"],
            "human": d["human"],
        }
        async for d in cursor
    ]

    # User signups trend
    user_pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                    "day": {"$dayOfMonth": "$created_at"},
                },
                "signups": {"$sum": 1},
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}},
    ]
    user_cursor = db.users.aggregate(user_pipeline)
    user_signups = [
        {
            "date": f"{d['_id']['year']}-{d['_id']['month']:02d}-{d['_id']['day']:02d}",
            "signups": d["signups"],
        }
        async for d in user_cursor
    ]

    return {"daily_predictions": daily, "user_signups": user_signups, "days": days}
