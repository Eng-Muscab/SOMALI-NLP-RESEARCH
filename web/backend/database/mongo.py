import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from ..config import settings

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


async def connect() -> AsyncIOMotorDatabase:
    global client, db
    if client is None:
        client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
        )
        db = client[settings.mongo_db_name]

    try:
        from ..services.auth_service import ensure_demo_user

        await ensure_demo_user()
    except Exception:
        logger.exception(
            "Failed to create/refresh the demo account (demo@somalinlp.io). "
            "Login with that account will fail with 'Invalid credentials' until this is fixed — "
            "check that MongoDB is running and reachable."
        )

    return get_database()


async def close() -> None:
    global client, db
    if client is not None:
        client.close()
    client = None
    db = None


def get_database() -> AsyncIOMotorDatabase:
    if db is None:
        raise RuntimeError("MongoDB is not connected")
    return db


async def ping() -> bool:
    if client is None:
        return False
    try:
        await client.admin.command("ping")
    except Exception:
        return False
    return True
