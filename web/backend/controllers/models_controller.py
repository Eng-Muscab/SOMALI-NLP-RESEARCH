import csv
from pathlib import Path

from fastapi import APIRouter

from ..config import settings
from ..services.ml_service import ml_service

router = APIRouter(prefix="/models", tags=["models"])


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


def _load_all_csv_models() -> list[dict]:
    """Read all models from two_experiment_model_comparison.csv (primary)
    and fall back to per-experiment all_models_comparison.csv for any gaps."""
    seen: set[str] = set()
    rows: list[dict] = []

    # Primary: two_experiment_model_comparison.csv (has all 29 models)
    for path in sorted(settings.experiments_dir.glob(
            "experiment_*/results/two_experiment_model_comparison.csv")):
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                uid = f"{row.get('experiment','')}__{row.get('model','')}"
                if uid not in seen:
                    seen.add(uid)
                    rows.append(dict(row))
        break  # identical file in every experiment dir – read once

    # Fallback: per-experiment all_models_comparison.csv
    for path in sorted(settings.experiments_dir.glob(
            "experiment_*/results/all_models_comparison.csv")):
        exp = path.parent.parent.name
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                uid = f"{exp}__{row.get('model','')}"
                if uid not in seen:
                    seen.add(uid)
                    r = dict(row)
                    r.setdefault("experiment", exp)
                    rows.append(r)

    rows.sort(key=lambda r: _as_float(r.get("accuracy")), reverse=True)
    return rows


def _find_ml_key(experiment: str, model_name: str, loaded: set[str]) -> str | None:
    """Try common key patterns to find a match in ml_service."""
    exp_lo  = experiment.lower()
    mod_lo  = model_name.lower()
    candidates = [
        f"{exp_lo}_{mod_lo}",           # experiment_1_stopwords_included_linearsvc_tfidf
        mod_lo,                          # linearsvc_tfidf
        mod_lo.replace("_tfidf", ""),    # linearsvc
        f"{exp_lo}_{mod_lo.replace('_tfidf','')}",
    ]
    # Special aliases
    aliases = {
        "xlmroberta_finetuned": "xlm-roberta-base",
        "linearsvc_tfidf":      "linear_svc_tfidf",
    }
    if mod_lo in aliases:
        candidates += [
            aliases[mod_lo],
            f"{exp_lo}_{aliases[mod_lo]}",
        ]
    for c in candidates:
        if c in loaded:
            return c
    # Fuzzy: check if any loaded key ends with the model name
    for k in loaded:
        if k.endswith(mod_lo) or k.endswith(mod_lo.replace("_tfidf", "")):
            return k
    return None


@router.post("/reload")
async def reload_models():
    ml_service.load_models()
    return {
        "status": "ok",
        "models_loaded": len(ml_service.list_models()),
        "models": ml_service.list_models(),
        "load_errors": ml_service.load_errors,
    }


@router.get("")
async def list_models():
    csv_rows = _load_all_csv_models()
    loaded: set[str] = set(ml_service.list_models())
    models = []

    for row in csv_rows:
        experiment  = row.get("experiment", "")
        model_name  = row.get("model", "")
        ml_key      = _find_ml_key(experiment, model_name, loaded)

        model_data  = ml_service.models.get(ml_key)      if ml_key else None
        path_val    = ml_service.model_paths.get(ml_key) if ml_key else None
        model_type  = (model_data["type"] if model_data else None) or row.get("family", "unknown")

        models.append({
            "id":             ml_key or f"{experiment}__{model_name}".lower(),
            "name":           model_name,
            "type":           row.get("family") or model_type,
            "experiment":     experiment,
            "experimentName": experiment.replace("_", " ").title() if experiment else "Unassigned",
            "accuracy":       round(_as_float(row.get("accuracy")) * 100, 2),
            "precision":      round(_as_float(row.get("precision")), 3),
            "recall":         round(_as_float(row.get("recall")), 3),
            "f1":             round(_as_float(row.get("f1")), 3),
            "status":         "active" if ml_key else "unavailable",
            "path":           path_val,
        })

    return models
