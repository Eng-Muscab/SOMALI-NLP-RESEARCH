import logging
import os
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..config import settings
from ..database.mongo import get_database
from ..models.user import ROLE_LIMITS, UserRole
from ..utils.security import hash_password, verify_password
from ..utils.jwt import create_access_token

logger = logging.getLogger(__name__)


async def ensure_user_indexes() -> None:
    db = get_database()
    await db.users.create_index("email", unique=True)
    await db.activity_logs.create_index("created_at")
    await db.activity_logs.create_index("user_email")
    await db.predictions.create_index("created_at")
    await db.submitted_articles.create_index("created_at")
    await db.submitted_articles.create_index("category")


async def ensure_demo_user() -> None:
    """Seed the shared demo account, if this deployment is configured to have one.

    The account exists so a supervisor or examiner can sign in without being
    registered by hand. It used to be created unconditionally as SUPER_ADMIN with
    the password `Demo12345!` written in this file -- and this repository is
    public, so on a reachable deployment that published a super-administrator to
    anyone who read the source: delete any user, change any role, export the
    submitted-article corpus. Worse, it ran on every start-up and reset the
    password, so changing it in the database did not hold.

    A deployment now opts in. Set DEMO_USER_PASSWORD to enable the account, and
    DEMO_USER_ROLE to decide how much it may do -- `viewer` is enough to sign in
    and classify text, which is what a demonstration needs. With no password set,
    production seeds nothing; outside production the old convenience is kept so
    that a local checkout still logs straight in.
    """
    db = get_database()
    await ensure_user_indexes()

    demo_email = os.getenv("DEMO_USER_EMAIL", "demo@somalinlp.io")
    demo_password = os.getenv("DEMO_USER_PASSWORD", "")
    demo_role = os.getenv("DEMO_USER_ROLE", UserRole.VIEWER)

    if not demo_password:
        if settings.environment == "production":
            logger.info(
                "No DEMO_USER_PASSWORD set; not seeding a demo account. "
                "Create administrators with deploy/make-admin.sh."
            )
            return
        demo_password = "Demo12345!"
        demo_role = UserRole.SUPER_ADMIN

    if demo_role not in set(ROLE_LIMITS):
        logger.warning("DEMO_USER_ROLE=%r is not a role; falling back to viewer", demo_role)
        demo_role = UserRole.VIEWER

    limits = ROLE_LIMITS[demo_role]

    existing = await db.users.find_one({"email": demo_email})
    update_doc = {
        "password": hash_password(demo_password),
        "is_active": True,
        "role": demo_role,
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
