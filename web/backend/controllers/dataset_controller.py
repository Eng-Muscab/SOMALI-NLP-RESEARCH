from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
from datetime import datetime

from ..config import settings
from ..database.mongo import get_database
from ..models.dataset import DatasetDocument

router = APIRouter(prefix="/datasets", tags=["datasets"])
UPLOAD_DIR = Path(settings.uploads_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    db = get_database()
    dest = UPLOAD_DIR / f"{int(datetime.utcnow().timestamp())}_{file.filename}"
    try:
        contents = await file.read()
        with open(dest, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    meta = DatasetDocument(
        filename=file.filename,
        path=str(dest),
        size=len(contents),
        uploaded_at=datetime.utcnow(),
    )
    await db.datasets.insert_one(meta.model_dump())
    return {"status": "ok", "meta": meta.model_dump()}


@router.get("")
async def list_datasets():
    db = get_database()
    items = []
    cursor = db.datasets.find().sort("uploaded_at", -1)
    async for d in cursor:
        d["id"] = str(d.get("_id"))
        d.pop("_id", None)
        items.append(d)
    return items
