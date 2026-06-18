import csv
from bson import ObjectId
from fastapi import APIRouter, UploadFile, File, HTTPException
from pymongo.errors import PyMongoError
from pathlib import Path
from datetime import datetime

from ..config import settings
from ..database.mongo import get_database
from ..models.dataset import DatasetDocument

router = APIRouter(prefix="/datasets", tags=["datasets"])
UPLOAD_DIR = Path(settings.uploads_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _database_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Database is unavailable. Please start MongoDB and try again.",
    )


def _serialize_dataset(document: dict) -> dict:
    filename = document.get("filename", "")
    suffix = Path(filename).suffix.replace(".", "").upper() or "FILE"
    uploaded_at = document.get("uploaded_at")
    return {
        "id": str(document.get("_id") or document.get("id")),
        "filename": filename,
        "size": document.get("size", 0),
        "type": suffix,
        "uploadedAt": uploaded_at.isoformat() if hasattr(uploaded_at, "isoformat") else uploaded_at,
        "rowCount": document.get("row_count"),
        "columnCount": document.get("column_count"),
    }


def _read_csv_preview(path: Path, limit: int = 10) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        dialect = csv.Sniffer().sniff(sample) if sample else csv.excel
        reader = csv.reader(handle, dialect)
        rows = list(reader)

    if not rows:
        return [], []

    columns = [str(column) for column in rows[0]]
    preview_rows = [[str(cell) for cell in row] for row in rows[1 : limit + 1]]
    return columns, preview_rows


def _csv_stats(path: Path) -> tuple[int | None, int | None]:
    try:
        columns, rows = _read_csv_preview(path, limit=1000000)
    except Exception:
        return None, None
    return len(rows), len(columns)


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    try:
        db = get_database()
    except (RuntimeError, PyMongoError) as exc:
        raise _database_unavailable(exc) from exc
    dest = UPLOAD_DIR / f"{int(datetime.utcnow().timestamp())}_{file.filename}"
    try:
        contents = await file.read()
        with open(dest, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    row_count, column_count = _csv_stats(dest) if dest.suffix.lower() == ".csv" else (None, None)
    meta = DatasetDocument(
        filename=file.filename,
        path=str(dest),
        size=len(contents),
        uploaded_at=datetime.utcnow(),
    )
    document = meta.model_dump()
    document["row_count"] = row_count
    document["column_count"] = column_count
    try:
        result = await db.datasets.insert_one(document)
    except PyMongoError as exc:
        raise _database_unavailable(exc) from exc
    document["_id"] = result.inserted_id
    return {"status": "ok", "meta": _serialize_dataset(document)}


@router.get("")
async def list_datasets():
    try:
        db = get_database()
    except (RuntimeError, PyMongoError) as exc:
        raise _database_unavailable(exc) from exc
    items = []
    try:
        cursor = db.datasets.find().sort("uploaded_at", -1)
        async for d in cursor:
            items.append(_serialize_dataset(d))
    except PyMongoError as exc:
        raise _database_unavailable(exc) from exc
    return items


@router.get("/{dataset_id}/preview")
async def preview_dataset(dataset_id: str):
    if not ObjectId.is_valid(dataset_id):
        raise HTTPException(status_code=400, detail="Invalid dataset id")

    try:
        db = get_database()
        document = await db.datasets.find_one({"_id": ObjectId(dataset_id)})
    except (RuntimeError, PyMongoError) as exc:
        raise _database_unavailable(exc) from exc
    if not document:
        raise HTTPException(status_code=404, detail="Dataset not found")

    path = Path(document.get("path", ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found")

    if path.suffix.lower() != ".csv":
        return {
            "id": dataset_id,
            "filename": document.get("filename", path.name),
            "columns": ["Message"],
            "rows": [["Preview is currently available for CSV files."]],
        }

    try:
        columns, rows = _read_csv_preview(path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Unable to preview dataset: {exc}") from exc

    return {
        "id": dataset_id,
        "filename": document.get("filename", path.name),
        "columns": columns,
        "rows": rows,
    }


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str):
    if not ObjectId.is_valid(dataset_id):
        raise HTTPException(status_code=400, detail="Invalid dataset id")

    try:
        db = get_database()
        document = await db.datasets.find_one({"_id": ObjectId(dataset_id)})
    except (RuntimeError, PyMongoError) as exc:
        raise _database_unavailable(exc) from exc
    if not document:
        raise HTTPException(status_code=404, detail="Dataset not found")

    path = Path(document.get("path", ""))
    if path.exists() and path.is_file():
        path.unlink()

    try:
        await db.datasets.delete_one({"_id": ObjectId(dataset_id)})
    except PyMongoError as exc:
        raise _database_unavailable(exc) from exc
    return {"status": "ok"}
