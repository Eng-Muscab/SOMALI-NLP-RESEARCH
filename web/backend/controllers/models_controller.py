import csv
from pathlib import Path

from fastapi import APIRouter

from ..config import settings
from ..services.ml_service import ml_service

router = APIRouter(prefix="/models", tags=["models"])


def _metric_keys(row: dict[str, str]) -> list[str]:
    experiment = row.get("experiment", "").lower()
    model = row.get("model", "").lower()
    keys = [f"{experiment}_{model}", model]

    aliases = {
        "xlmroberta_finetuned": "xlm-roberta-base",
        "linearsvc_tfidf": "linear_svc_tfidf",
    }
    if model in aliases:
        keys.append(f"{experiment}_{aliases[model]}")
        keys.append(aliases[model])
    return keys


def _load_metrics() -> dict[str, dict[str, str]]:
    metrics: dict[str, dict[str, str]] = {}
    for path in settings.experiments_dir.glob("experiment_*/*/all_models_comparison.csv"):
        # This glob supports older layouts if present, but current results live under results/.
        if path.parent.name != "results":
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for key in _metric_keys(row):
                    metrics[key] = row
    for path in settings.experiments_dir.glob("experiment_*/results/all_models_comparison.csv"):
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for key in _metric_keys(row):
                    metrics[key] = row
    return metrics


def _as_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


def _experiment_from_path(path: str | None) -> str | None:
    if not path:
        return None
    parts = Path(path).parts
    return next((part for part in parts if part.lower().startswith("experiment_")), None)


@router.get("")
async def list_models():
    metrics = _load_metrics()
    models = []

    for key in ml_service.list_models():
        model_data = ml_service.models.get(key)
        path = ml_service.model_paths.get(key)
        model_type = model_data["type"] if model_data else "unknown"
        experiment = _experiment_from_path(path)
        metric = metrics.get(key, metrics.get(key.split("_")[-1], {}))
        display_name = metric.get("model") or key.replace("_", " ").title()

        models.append(
            {
                "id": key,
                "name": display_name,
                "type": metric.get("family") or model_type,
                "experiment": experiment,
                "experimentName": experiment.replace("_", " ").title() if experiment else "Unassigned",
                "accuracy": round(_as_float(metric.get("accuracy")) * 100, 2),
                "precision": round(_as_float(metric.get("precision")), 3),
                "recall": round(_as_float(metric.get("recall")), 3),
                "f1": round(_as_float(metric.get("f1")), 3),
                "status": "active",
                "path": path,
            }
        )

    return models
