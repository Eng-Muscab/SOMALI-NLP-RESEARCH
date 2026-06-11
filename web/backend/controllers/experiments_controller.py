from fastapi import APIRouter
from pathlib import Path
import json

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("")
async def list_experiments():
    root = Path(__file__).resolve().parents[3].parent / "experiments"
    results = []
    if not root.exists():
        return results
    # gather top-level summary files
    for p in root.glob("*.json"):
        try:
            data = json.loads(p.read_text())
            results.append({"file": p.name, "data": data})
        except Exception:
            continue
    # gather per-experiment folders
    for d in root.iterdir():
        if d.is_dir():
            summary = d / "experiment_summary.json"
            if summary.exists():
                try:
                    data = json.loads(summary.read_text())
                    results.append({"file": str(summary), "data": data})
                except Exception:
                    continue
    return results
