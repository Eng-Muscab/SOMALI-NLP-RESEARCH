from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from ..database.mongo import get_database
from ..models.user import UserRole
from ..utils.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _is_admin(current_user: dict) -> bool:
    return current_user.get("role") in {UserRole.ADMIN, UserRole.SUPER_ADMIN}


def _own_filter(current_user: dict) -> dict:
    return {"user_id": current_user.get("id", "")}


@router.get("/overview")
async def get_overview(current_user: dict = Depends(get_current_user)):
    db = get_database()
    admin = _is_admin(current_user)
    scope = {} if admin else _own_filter(current_user)

    total_predictions = await db.predictions.count_documents(scope)
    ai_predictions = await db.predictions.count_documents({**scope, "prediction": "AI"})
    human_predictions = await db.predictions.count_documents({**scope, "prediction": "HUMAN"})
    total_users = await db.users.count_documents({}) if admin else None
    active_users = await db.users.count_documents({"is_active": True}) if admin else None

    # Today's predictions
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_predictions = await db.predictions.count_documents({**scope, "created_at": {"$gte": today_start}})

    # This month
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_predictions = await db.predictions.count_documents({**scope, "created_at": {"$gte": month_start}})

    # Most used models (top 5)
    pipeline = [
        *([{"$match": scope}] if scope else []),
        {"$group": {"_id": "$model", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    model_cursor = db.predictions.aggregate(pipeline)
    top_models = [{"model": d["_id"], "count": d["count"]} async for d in model_cursor]

    # Average confidence
    conf_pipeline = [
        *([{"$match": scope}] if scope else []),
        {"$group": {"_id": None, "avg_confidence": {"$avg": "$confidence"}}},
    ]
    conf_result = await db.predictions.aggregate(conf_pipeline).to_list(1)
    avg_confidence = round(conf_result[0]["avg_confidence"] * 100, 1) if conf_result else 0

    return {
        "scope": "platform" if admin else "personal",
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
    granularity: str = Query("day", pattern="^(day|month|year)$"),
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    admin = _is_admin(current_user)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    match: dict = {"created_at": {"$gte": since}}
    if not admin:
        match.update(_own_filter(current_user))

    if granularity == "year":
        group_id = {"year": {"$year": "$created_at"}}
        fmt = lambda d: f"{d['_id']['year']}"  # noqa: E731
    elif granularity == "month":
        group_id = {"year": {"$year": "$created_at"}, "month": {"$month": "$created_at"}}
        fmt = lambda d: f"{d['_id']['year']}-{d['_id']['month']:02d}"  # noqa: E731
    else:
        group_id = {
            "year": {"$year": "$created_at"},
            "month": {"$month": "$created_at"},
            "day": {"$dayOfMonth": "$created_at"},
        }
        fmt = lambda d: f"{d['_id']['year']}-{d['_id']['month']:02d}-{d['_id']['day']:02d}"  # noqa: E731

    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": group_id,
                "total": {"$sum": 1},
                "ai": {"$sum": {"$cond": [{"$eq": ["$prediction", "AI"]}, 1, 0]}},
                "human": {"$sum": {"$cond": [{"$eq": ["$prediction", "HUMAN"]}, 1, 0]}},
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}},
    ]
    cursor = db.predictions.aggregate(pipeline)
    series = [
        {"date": fmt(d), "total": d["total"], "ai": d["ai"], "human": d["human"]}
        async for d in cursor
    ]

    # User signups trend (platform-wide — admin only; not meaningful for a personal report)
    user_signups: list[dict] = []
    if admin:
        user_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": group_id, "signups": {"$sum": 1}}},
            {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}},
        ]
        user_cursor = db.users.aggregate(user_pipeline)
        user_signups = [{"date": fmt(d), "signups": d["signups"]} async for d in user_cursor]

    return {
        "scope": "platform" if admin else "personal",
        "daily_predictions": series,
        "user_signups": user_signups,
        "days": days,
        "granularity": granularity,
    }


@router.get("/by-category")
async def get_by_category(
    days: int = Query(30, ge=1, le=3650),
    current_user: dict = Depends(get_current_user),
):
    """Breakdown of tested/predicted articles by topical category."""
    db = get_database()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    match: dict = {"created_at": {"$gte": since}}
    if not _is_admin(current_user):
        match.update(_own_filter(current_user))

    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {"$ifNull": ["$category", "Unknown"]},
                "total": {"$sum": 1},
                "ai": {"$sum": {"$cond": [{"$eq": ["$prediction", "AI"]}, 1, 0]}},
                "human": {"$sum": {"$cond": [{"$eq": ["$prediction", "HUMAN"]}, 1, 0]}},
                "avg_confidence": {"$avg": "$confidence"},
            }
        },
        {"$sort": {"total": -1}},
    ]
    cursor = db.predictions.aggregate(pipeline)
    categories = [
        {
            "category": d["_id"],
            "total": d["total"],
            "ai": d["ai"],
            "human": d["human"],
            "avg_confidence": round((d["avg_confidence"] or 0) * 100, 1),
        }
        async for d in cursor
    ]
    return {"categories": categories, "days": days, "scope": "platform" if _is_admin(current_user) else "personal"}


@router.get("/by-user")
async def get_by_user(
    days: int = Query(30, ge=1, le=3650),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_admin),
):
    """Which users have been testing the system the most (usage leaderboard)."""
    db = get_database()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"created_at": {"$gte": since}, "user_email": {"$nin": [None, ""]}}},
        {
            "$group": {
                "_id": "$user_email",
                "total": {"$sum": 1},
                "ai": {"$sum": {"$cond": [{"$eq": ["$prediction", "AI"]}, 1, 0]}},
                "human": {"$sum": {"$cond": [{"$eq": ["$prediction", "HUMAN"]}, 1, 0]}},
                "last_used": {"$max": "$created_at"},
            }
        },
        {"$sort": {"total": -1}},
        {"$limit": limit},
    ]
    cursor = db.predictions.aggregate(pipeline)
    users = [
        {
            "email": d["_id"],
            "total": d["total"],
            "ai": d["ai"],
            "human": d["human"],
            "last_used": d["last_used"].isoformat() if d.get("last_used") else None,
        }
        async for d in cursor
    ]
    return {"users": users, "days": days}
