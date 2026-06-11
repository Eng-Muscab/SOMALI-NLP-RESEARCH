from fastapi import APIRouter

from ..config import settings
from ..database.mongo import ping

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    mongo_ok = await ping()
    return {
        "status": "ok" if mongo_ok else "degraded",
        "database": "connected" if mongo_ok else "disconnected",
        "environment": settings.environment,
    }
