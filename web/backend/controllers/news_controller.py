from fastapi import APIRouter, Depends, HTTPException, status

from ..services.external_news_service import SOURCES, get_source
from ..utils.dependencies import get_current_user

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/sources")
async def list_sources(current_user: dict = Depends(get_current_user)):
    return [{"id": source_id, "name": info["name"]} for source_id, info in SOURCES.items()]


@router.get("/external")
async def external_news(
    source: str,
    limit: int = 20,
    force: bool = False,
    current_user: dict = Depends(get_current_user),
):
    if source not in SOURCES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown news source.")
    limit = max(1, min(limit, 50))
    return await get_source(source, limit, force=force)
