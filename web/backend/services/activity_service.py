from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..database.mongo import get_database

logger = logging.getLogger(__name__)


async def log_activity(
    *,
    user_id: str,
    user_email: str,
    user_name: str = "",
    action: str,
    category: str,
    details: dict | None = None,
    status: str = "success",
    ip_address: str | None = None,
) -> None:
    try:
        db = get_database()
        await db.activity_logs.insert_one(
            {
                "user_id": user_id,
                "user_email": user_email,
                "user_name": user_name,
                "action": action,
                "category": category,
                "details": details or {},
                "status": status,
                "ip_address": ip_address,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        logger.warning("Failed to write activity log for %s / %s", user_email, action)


def _serialize_log(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "user_id": doc.get("user_id", ""),
        "user_email": doc.get("user_email", ""),
        "user_name": doc.get("user_name", ""),
        "action": doc.get("action", ""),
        "category": doc.get("category", ""),
        "details": doc.get("details", {}),
        "status": doc.get("status", "success"),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)).isoformat()
        if hasattr(doc.get("created_at"), "isoformat")
        else str(doc.get("created_at", "")),
    }


async def get_logs(
    *,
    limit: int = 50,
    skip: int = 0,
    category: str | None = None,
    user_email: str | None = None,
    action: str | None = None,
) -> list[dict]:
    db = get_database()
    query: dict = {}
    if category:
        query["category"] = category
    if user_email:
        query["user_email"] = {"$regex": user_email, "$options": "i"}
    if action:
        query["action"] = action

    cursor = db.activity_logs.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_serialize_log(d) for d in docs]


async def count_logs(
    *,
    category: str | None = None,
    user_email: str | None = None,
    action: str | None = None,
) -> int:
    db = get_database()
    query: dict = {}
    if category:
        query["category"] = category
    if user_email:
        query["user_email"] = {"$regex": user_email, "$options": "i"}
    if action:
        query["action"] = action
    return await db.activity_logs.count_documents(query)
