import csv

from fastapi import APIRouter, HTTPException

from ..config import settings

router = APIRouter()


def _as_percent(value: str | None) -> float:
    raw = float(value or 0.0)
    percent = raw * 100 if 0.0 < raw <= 1.0 else raw
    return round(percent, 2)



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
    csv_paths = list(settings.experiments_dir.glob("experiment_*/results/all_models_comparison.csv"))
    if not csv_paths:
        csv_paths = list(settings.experiments_dir.rglob("*all_models_comparison.csv"))

    for path in csv_paths:
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                for raw_row in csv.DictReader(handle):
                    if not raw_row:
                        continue
                    row = {k.strip().lower(): v for k, v in raw_row.items() if k}
                    acc = _as_percent(row.get("accuracy"))
                    prec = _as_percent(row.get("precision"))
                    rec = _as_percent(row.get("recall"))
                    f1_val = _as_percent(row.get("f1"))
                    macro_val = _as_percent(row.get("macro_f1"))

                    payload = {
                        "experiment": row.get("experiment"),
                        "family": row.get("family"),
                        "model": row.get("model"),
                        "accuracy": acc,
                        "precision": prec,
                        "recall": rec,
                        "f1": f1_val,
                        "macro_f1": macro_val,
                        "test_rows": int(float(row.get("test_rows") or row.get("test_size") or 0)),
                    }
                    for key in _metric_keys(row):
                        metrics[key] = payload
        except Exception:
            continue
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


