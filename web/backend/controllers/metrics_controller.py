import csv

from fastapi import APIRouter, HTTPException

from ..config import settings

router = APIRouter()


def _metric_keys(row: dict[str, str]) -> list[str]:
    experiment = row.get("experiment", "").lower()
    model = row.get("model", "").lower()
    keys = [model, f"{experiment}_{model}"]
    aliases = {
        "xlmroberta_finetuned": "xlm-roberta-base",
        "linearsvc_tfidf": "linear_svc_tfidf",
    }
    if model in aliases:
        keys.extend([aliases[model], f"{experiment}_{aliases[model]}"])
    return keys


def _load_metrics() -> dict[str, dict[str, object]]:
    metrics: dict[str, dict[str, object]] = {}
    for path in settings.experiments_dir.glob("experiment_*/results/all_models_comparison.csv"):
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                payload = {
                    "experiment": row.get("experiment"),
                    "family": row.get("family"),
                    "model": row.get("model"),
                    "accuracy": float(row.get("accuracy") or 0.0),
                    "precision": float(row.get("precision") or 0.0),
                    "recall": float(row.get("recall") or 0.0),
                    "f1": float(row.get("f1") or 0.0),
                    "macro_f1": float(row.get("macro_f1") or 0.0),
                    "test_rows": int(float(row.get("test_rows") or 0)),
                }
                for key in _metric_keys(row):
                    metrics[key] = payload
    return metrics


@router.get("/metrics", summary="Get evaluation metrics for all experiment models")
async def get_all_metrics():
    return _load_metrics()


@router.get("/metrics/{model_key}", summary="Get metrics for a specific model")
async def get_model_metrics(model_key: str):
    metrics = _load_metrics()
    key = model_key.lower()
    if key not in metrics:
        raise HTTPException(status_code=404, detail=f"Metrics for model '{model_key}' not found")
    return metrics[key]
