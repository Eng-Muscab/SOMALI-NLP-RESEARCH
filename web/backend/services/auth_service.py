from datetime import datetime

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..config import settings
from ..database.mongo import get_database
from ..models.user import UserDocument
from ..utils.security import hash_password, verify_password
from ..utils.jwt import create_access_token

async def ensure_user_indexes() -> None:
    db = get_database()
    await db.users.create_index("email", unique=True)


def serialize_user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {
        "id": str(user.get("_id")),
        "email": user.get("email"),
    }


async def register_user(email: str, password: str):
    db = get_database()
    normalized_email = email.strip().lower()
    await ensure_user_indexes()
    user = await db.users.find_one({"email": normalized_email})
    if user:
        return None
    hashed = hash_password(password)
    new_user = UserDocument(
        email=normalized_email,
        password=hashed,
        created_at=datetime.utcnow(),
    )
    try:
        res = await db.users.insert_one(new_user.model_dump())
    except DuplicateKeyError:
        return None
    return {"id": str(res.inserted_id), "email": normalized_email}

async def authenticate_user(email: str, password: str):
    db = get_database()
    normalized_email = email.strip().lower()
    user = await db.users.find_one({"email": normalized_email})
    if not user:
        return None
    if not verify_password(password, user.get("password")):
        return None
    if not user.get("is_active", True):
        return None
    return {
        "access_token": create_access_token(str(user.get("_id"))),
        "expires_in": settings.access_token_expire_minutes * 60,
    }


async def get_user_by_id(user_id: str):
    if not ObjectId.is_valid(user_id):
        return None
    db = get_database()
    user = await db.users.find_one({"_id": ObjectId(user_id), "is_active": {"$ne": False}})
    return serialize_user(user)
