import csv
from pathlib import Path

from fastapi import APIRouter

from ..config import REPO_ROOT, settings
from ..services.ml_service import ml_service

router = APIRouter(prefix="/models", tags=["models"])


def _as_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


def _as_percent(value: str | None) -> float:
    raw = _as_float(value)
    percent = raw * 100 if 0.0 < raw <= 1.0 else raw
    return round(percent, 2)


def _experiment_from_path(path: str | None) -> str | None:
    if not path:
        return None
    parts = Path(path).parts
    return next((part for part in parts if part.lower().startswith("experiment_")), None)


def _load_all_csv_models() -> list[dict]:
    """Read all models from per-experiment all_models_comparison.csv."""
    seen: set[str] = set()
    rows: list[dict] = []

    csv_paths = list(settings.experiments_dir.glob("experiment_*/results/all_models_comparison.csv"))
    if not csv_paths:
        csv_paths = list(settings.experiments_dir.glob("experiment_*/evaluation/reports/step9_metrics.csv"))
    if not csv_paths:
        csv_paths = list(REPO_ROOT.rglob("*all_models_comparison.csv"))
    if not csv_paths:
        csv_paths = list(REPO_ROOT.rglob("*step9_metrics.csv"))

    csv_paths = [
        p for p in csv_paths
        if "node_modules" not in p.parts and ".venv" not in p.parts and "venv" not in p.parts
    ]
    csv_paths.sort(key=lambda p: ("results" not in p.parts, str(p)))

    for path in csv_paths:
        exp = path.parent.parent.name if path.parent and path.parent.parent else "experiment_1"
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                for raw_row in csv.DictReader(fh):
                    if not raw_row:
                        continue
                    norm_row = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items() if k}
                    exp_id = norm_row.get("experiment") or exp
                    mod_name = norm_row.get("model") or ""
                    if not mod_name:
                        continue
                    uid = f"{exp_id}__{mod_name}"
                    if uid not in seen:
                        seen.add(uid)
                        r = dict(norm_row)
                        r.setdefault("experiment", exp_id)
                        r.setdefault("model", mod_name)
                        rows.append(r)
        except Exception:
            continue

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
    # Fuzzy fallback: only match keys that belong to THIS experiment, never
    # borrow another experiment's model file (that would silently mislabel
    # predictions as coming from the wrong training run).
    for k in loaded:
        if not k.startswith(exp_lo):
            continue
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

        # Deliberately not `ml_service.models[...]`: that would load the model just to
        # read its family, and this endpoint asks about every model on every request.
        path_val    = ml_service.model_paths.get(ml_key) if ml_key else None
        model_type  = (ml_service.model_type(ml_key) if ml_key else None) or row.get("family", "unknown")

        acc = _as_percent(row.get("accuracy"))
        prec = _as_percent(row.get("precision"))
        rec = _as_percent(row.get("recall"))
        f1_final = _as_percent(row.get("f1"))

        models.append({
            "id":             ml_key or f"{experiment}__{model_name}".lower(),
            "name":           model_name,
            "type":           row.get("family") or model_type,
            "experiment":     experiment,
            "experimentName": experiment.replace("_", " ").title() if experiment else "Unassigned",
            "accuracy":       acc,
            "precision":      prec,
            "recall":         rec,
            "f1":             f1_final,
            "status":         "active" if ml_key else "unavailable",
            "path":           path_val,
        })

    return models


