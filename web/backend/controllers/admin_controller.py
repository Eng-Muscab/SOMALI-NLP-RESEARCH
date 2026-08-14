from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pymongo.errors import DuplicateKeyError

from ..database.mongo import get_database
from ..models.user import ROLE_LIMITS, UserRole
from ..schemas.user import AdminUserCreate, AdminUserOut, AdminUserUpdate, ResetPasswordRequest
from ..services.activity_service import log_activity
from ..utils.dependencies import get_current_user, require_admin, require_super_admin
from ..utils.security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def _serialize_user(doc: dict) -> dict:
    created = doc.get("created_at")
    last_login = doc.get("last_login")
    return {
        "id": str(doc["_id"]),
        "email": doc.get("email", ""),
        "name": doc.get("name", ""),
        "role": doc.get("role", UserRole.VIEWER),
        "is_active": doc.get("is_active", True),
        "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
        "last_login": last_login.isoformat() if hasattr(last_login, "isoformat") else None,
        "daily_prediction_count": doc.get("daily_prediction_count", 0),
        "monthly_prediction_count": doc.get("monthly_prediction_count", 0),
        "daily_prediction_limit": doc.get("daily_prediction_limit", -1),
        "monthly_prediction_limit": doc.get("monthly_prediction_limit", 200),
        "max_text_length": doc.get("max_text_length", -1),
    }


# ── List users ────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    role: str = Query(""),
    status_filter: str = Query("", alias="status"),
    current_user: dict = Depends(require_admin),
):
    db = get_database()
    query: dict = {}
    if search:
        query["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
        ]
    if role:
        query["role"] = role
    if status_filter == "active":
        query["is_active"] = True
    elif status_filter == "suspended":
        query["is_active"] = False

    skip = (page - 1) * limit
    total = await db.users.count_documents(query)
    cursor = db.users.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, (total + limit - 1) // limit),
        "users": [_serialize_user(d) for d in docs],
    }


# ── Create user ───────────────────────────────────────────────────────────────

@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: AdminUserCreate,
    current_user: dict = Depends(require_admin),
):
    db = get_database()
    if await db.users.find_one({"email": body.email}):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    limits = ROLE_LIMITS.get(body.role, ROLE_LIMITS[UserRole.VIEWER])
    doc = {
        "email": body.email,
        "name": body.name,
        "password": hash_password(body.password),
        "role": body.role,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "last_login": None,
        "daily_prediction_count": 0,
        "monthly_prediction_count": 0,
        "daily_prediction_limit": body.daily_prediction_limit if body.daily_prediction_limit != -1 else limits["daily"],
        "monthly_prediction_limit": body.monthly_prediction_limit if body.monthly_prediction_limit != 200 else limits["monthly"],
        "max_text_length": body.max_text_length if body.max_text_length != -1 else limits["max_text"],
        "last_count_reset": "",
        "last_month_reset": "",
    }
    try:
        res = await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    await log_activity(
        user_id=current_user["id"],
        user_email=current_user["email"],
        user_name=current_user.get("name", ""),
        action="user_created",
        category="admin",
        details={"created_email": body.email, "role": body.role},
    )
    doc["_id"] = res.inserted_id
    return _serialize_user(doc)


# ── Get single user ───────────────────────────────────────────────────────────

@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    current_user: dict = Depends(require_admin),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID.")
    db = get_database()
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _serialize_user(doc)


# ── Update user ───────────────────────────────────────────────────────────────

@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: AdminUserUpdate,
    current_user: dict = Depends(require_admin),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID.")
    db = get_database()
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Prevent demoting other super_admins unless caller is super_admin
    if doc.get("role") == UserRole.SUPER_ADMIN and current_user.get("role") != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admins can modify super admin accounts.")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return _serialize_user(doc)

    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    updated = await db.users.find_one({"_id": ObjectId(user_id)})

    await log_activity(
        user_id=current_user["id"],
        user_email=current_user["email"],
        user_name=current_user.get("name", ""),
        action="user_updated",
        category="admin",
        details={"target_id": user_id, "target_email": doc.get("email"), "fields": list(updates.keys())},
    )
    return _serialize_user(updated)


# ── Delete user ───────────────────────────────────────────────────────────────

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_super_admin),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID.")
    if user_id == current_user["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account.")

    db = get_database()
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    await db.users.delete_one({"_id": ObjectId(user_id)})
    await log_activity(
        user_id=current_user["id"],
        user_email=current_user["email"],
        user_name=current_user.get("name", ""),
        action="user_deleted",
        category="admin",
        details={"deleted_email": doc.get("email"), "deleted_id": user_id},
    )


# ── Suspend / Activate ────────────────────────────────────────────────────────

@router.post("/users/{user_id}/suspend")
async def suspend_user(user_id: str, current_user: dict = Depends(require_admin)):
    return await _toggle_active(user_id, False, current_user)


@router.post("/users/{user_id}/activate")
async def activate_user(user_id: str, current_user: dict = Depends(require_admin)):
    return await _toggle_active(user_id, True, current_user)


async def _toggle_active(user_id: str, active: bool, current_user: dict) -> dict:
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID.")
    db = get_database()
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": active}})
    updated = await db.users.find_one({"_id": ObjectId(user_id)})
    action = "user_activated" if active else "user_suspended"
    await log_activity(
        user_id=current_user["id"],
        user_email=current_user["email"],
        user_name=current_user.get("name", ""),
        action=action,
        category="admin",
        details={"target_email": doc.get("email")},
    )
    return _serialize_user(updated)


# ── Reset password ────────────────────────────────────────────────────────────

@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    current_user: dict = Depends(require_admin),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID.")
    db = get_database()
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password": hash_password(body.new_password)}},
    )
    await log_activity(
        user_id=current_user["id"],
        user_email=current_user["email"],
        user_name=current_user.get("name", ""),
        action="password_reset",
        category="admin",
        details={"target_email": doc.get("email")},
    )
    return {"status": "ok", "message": "Password updated successfully."}


# ── Activity logs ─────────────────────────────────────────────────────────────

@router.get("/logs")
async def get_activity_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    category: str = Query(""),
    user_email: str = Query(""),
    action: str = Query(""),
    current_user: dict = Depends(require_admin),
):
    from ..services.activity_service import count_logs, get_logs

    skip = (page - 1) * limit
    logs = await get_logs(
        limit=limit,
        skip=skip,
        category=category or None,
        user_email=user_email or None,
        action=action or None,
    )
    total = await count_logs(
        category=category or None,
        user_email=user_email or None,
        action=action or None,
    )
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, (total + limit - 1) // limit),
        "logs": logs,
    }


# ── Submitted-article archive (for growing future training datasets) ──────────

@router.get("/submitted-articles")
async def list_submitted_articles(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    category: str = Query(""),
    label: str = Query(""),
    current_user: dict = Depends(require_admin),
):
    db = get_database()
    query: dict = {}
    if category:
        query["category"] = category
    if label:
        query["predicted_label"] = label

    skip = (page - 1) * limit
    total = await db.submitted_articles.count_documents(query)
    cursor = db.submitted_articles.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, (total + limit - 1) // limit),
        "articles": [
            {
                "id": str(d["_id"]),
                "text": d.get("text", ""),
                "predicted_label": d.get("predicted_label", ""),
                "confidence": d.get("confidence"),
                "category": d.get("category", ""),
                "model": d.get("model", ""),
                "reviewed": d.get("reviewed", False),
                "created_at": d["created_at"].isoformat() if d.get("created_at") else None,
            }
            for d in docs
        ],
    }


@router.get("/submitted-articles/export")
async def export_submitted_articles(
    reviewed_only: bool = Query(False),
    current_user: dict = Depends(require_super_admin),
):
    """CSV export in the same Text/Label shape as data/raw/labeled text.xlsx,
    ready to be merged into a future dataset rebuild."""
    db = get_database()
    query: dict = {"reviewed": True} if reviewed_only else {}
    cursor = db.submitted_articles.find(query).sort("created_at", -1)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Text", "Label", "Category", "Confidence", "SubmittedAt"])
    async for d in cursor:
        writer.writerow([
            d.get("text", ""),
            d.get("predicted_label", ""),
            d.get("category", ""),
            d.get("confidence", ""),
            d["created_at"].isoformat() if d.get("created_at") else "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=submitted_articles_archive.csv"},
    )
