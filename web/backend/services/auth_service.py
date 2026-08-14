from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..config import settings
from ..database.mongo import get_database
from ..models.user import ROLE_LIMITS, UserRole
from ..utils.security import hash_password, verify_password
from ..utils.jwt import create_access_token


async def ensure_user_indexes() -> None:
    db = get_database()
    await db.users.create_index("email", unique=True)
    await db.activity_logs.create_index("created_at")
    await db.activity_logs.create_index("user_email")
    await db.predictions.create_index("created_at")
    await db.submitted_articles.create_index("created_at")
    await db.submitted_articles.create_index("category")


async def ensure_demo_user() -> None:
    db = get_database()
    await ensure_user_indexes()

    demo_email = "demo@somalinlp.io"
    demo_password = "Demo12345!"
    limits = ROLE_LIMITS[UserRole.SUPER_ADMIN]

    existing = await db.users.find_one({"email": demo_email})
    update_doc = {
        "password": hash_password(demo_password),
        "is_active": True,
        "role": UserRole.SUPER_ADMIN,
        "name": "Demo Admin",
        "daily_prediction_limit": limits["daily"],
        "monthly_prediction_limit": limits["monthly"],
        "max_text_length": limits["max_text"],
    }
    if existing:
        await db.users.update_one({"email": demo_email}, {"$set": update_doc})
        return

    try:
        await db.users.insert_one(
            {
                **update_doc,
                "email": demo_email,
                "created_at": datetime.now(timezone.utc),
                "last_login": None,
                "daily_prediction_count": 0,
                "monthly_prediction_count": 0,
                "last_count_reset": "",
                "last_month_reset": "",
            }
        )
    except DuplicateKeyError:
        pass


def serialize_user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {
        "id": str(user.get("_id")),
        "email": user.get("email"),
        "name": user.get("name", ""),
        "role": user.get("role", UserRole.VIEWER),
        "max_text_length": user.get("max_text_length", 50000),
    }


async def register_user(email: str, password: str, name: str = ""):
    db = get_database()
    normalized_email = email.strip().lower()
    await ensure_user_indexes()
    if await db.users.find_one({"email": normalized_email}):
        return None

    limits = ROLE_LIMITS[UserRole.VIEWER]
    hashed = hash_password(password)
    doc = {
        "email": normalized_email,
        "name": name,
        "password": hashed,
        "role": UserRole.VIEWER,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "last_login": None,
        "daily_prediction_count": 0,
        "monthly_prediction_count": 0,
        "daily_prediction_limit": limits["daily"],
        "monthly_prediction_limit": limits["monthly"],
        "max_text_length": limits["max_text"],
        "last_count_reset": "",
        "last_month_reset": "",
    }
    try:
        res = await db.users.insert_one(doc)
    except DuplicateKeyError:
        return None
    return {"id": str(res.inserted_id), "email": normalized_email, "name": name, "role": UserRole.VIEWER}


class AuthenticationError(Exception):
    """Raised with a specific, user-facing reason login failed."""


async def authenticate_user(email: str, password: str):
    db = get_database()
    normalized_email = email.strip().lower()
    user = await db.users.find_one({"email": normalized_email})
    if not user:
        raise AuthenticationError("No account found with this email. Check the email or register.")
    if not verify_password(password, user.get("password", "")):
        raise AuthenticationError("Incorrect password.")
    if not user.get("is_active", True):
        raise AuthenticationError("This account has been deactivated. Contact an administrator.")

    # Update last_login
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.now(timezone.utc)}},
    )

    user_out = serialize_user(user)
    return {
        "access_token": create_access_token(str(user["_id"])),
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": user_out,
    }


async def get_user_by_id(user_id: str):
    if not ObjectId.is_valid(user_id):
        return None
    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(user_id), "is_active": {"$ne": False}})
    return serialize_user(user)
