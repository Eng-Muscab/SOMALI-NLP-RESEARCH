import csv
import json
from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..config import REPO_ROOT, settings

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _as_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


def _load_rows(exp_dir):
    path = exp_dir / "results" / "all_models_comparison.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _load_summary(exp_dir):
    path = exp_dir / "results" / "experiment_summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


@router.get("/comparison")
async def get_model_comparison():
    rows = []
    for path in settings.experiments_dir.glob("experiment_*/results/two_experiment_model_comparison.csv"):
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                rows.append({
                    "experiment": row.get("experiment", ""),
                    "family": row.get("family", ""),
                    "model": row.get("model", ""),
                    "accuracy": round(_as_float(row.get("accuracy")) * 100, 2),
                    "precision": round(_as_float(row.get("precision")) * 100, 2),
                    "recall": round(_as_float(row.get("recall")) * 100, 2),
                    "f1": round(_as_float(row.get("f1")), 4),
                    "macro_f1": round(_as_float(row.get("macro_f1")), 4),
                    "test_rows": int(_as_float(str(row.get("test_rows", 0)))),
                    "train_scope": row.get("saved_model_train_scope", ""),
                })
    rows.sort(key=lambda r: r["accuracy"], reverse=True)
    return rows


@router.get("/xai/lime/{experiment}/{index}")
async def get_lime_explanation(experiment: str, index: int = 0):
    """Serve a pre-computed LIME HTML explanation file."""
    path = (
        settings.experiments_dir
        / experiment
        / "xai" / "outputs" / "lime"
        / f"lime_explanation_{index}.html"
    )
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"LIME explanation {index} not found for {experiment}",
        )
    html = path.read_text(encoding="utf-8")
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/xai/shap-plot/{experiment}")
async def get_shap_plot(experiment: str):
    path = (
        settings.experiments_dir
        / experiment
        / "xai" / "outputs" / "shap"
        / "shap_summary_plot.png"
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="SHAP summary plot not found")
    return Response(content=path.read_bytes(), media_type="image/png")


@router.get("/evaluation/confusion-matrix/{experiment}/{model_name}")
async def get_confusion_matrix(experiment: str, model_name: str):
    path = (
        settings.experiments_dir
        / experiment
        / "evaluation" / "figures"
        / f"confusion_matrix_{model_name}.png"
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="Confusion matrix not found")
    return Response(content=path.read_bytes(), media_type="image/png")


@router.get("/xai/shap/{experiment}")
async def get_shap_importance(experiment: str, limit: int = 25):
    path = (
        settings.experiments_dir
        / experiment
        / "xai" / "outputs" / "shap"
        / "shap_global_importance.csv"
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"SHAP data not found for {experiment}")
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append({
                "feature": row.get("feature", "").strip(),
                "importance": round(_as_float(row.get("mean_abs_shap")), 6),
            })
    rows.sort(key=lambda r: r["importance"], reverse=True)
    return rows[:limit]


@router.get("/xai/errors/{experiment}")
async def get_error_analysis(experiment: str):
    path = (
        settings.experiments_dir
        / experiment
        / "xai" / "outputs"
        / "error_analysis_sample.csv"
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Error analysis not found for {experiment}")
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append({
                "text": row.get("Text", ""),
                "true_label": row.get("true_label", ""),
                "predicted_label": row.get("predicted_label", ""),
            })
    return rows


@router.get("")
async def list_experiments():
    results = []
    for exp_dir in sorted(settings.experiments_dir.glob("experiment_*")):
        if not exp_dir.is_dir():
            continue
        rows = _load_rows(exp_dir)
        if not rows:
            continue
        rows.sort(key=lambda row: (_as_float(row.get("f1")), _as_float(row.get("accuracy"))), reverse=True)
        best = rows[0]
        summary = _load_summary(exp_dir)
        split_summary = summary.get("experiment", {}).get("splits", {})
        train_rows = split_summary.get("train", {}).get("rows", 0)
        val_rows = split_summary.get("val", {}).get("rows", 0)
        test_rows = split_summary.get("test", {}).get("rows", best.get("test_rows", 0))

        results.append(
            {
                "file": str((exp_dir / "results" / "all_models_comparison.csv").resolve().relative_to(REPO_ROOT)),
                "data": {
                    "id": exp_dir.name,
                    "name": exp_dir.name.replace("_", " ").title(),
                    "date": date.fromtimestamp(exp_dir.stat().st_mtime).isoformat(),
                    "status": "completed",
                    "accuracy": round(_as_float(best.get("accuracy")) * 100, 2),
                    "f1": round(_as_float(best.get("f1")), 3),
                    "models": len(rows),
                    "runtime": "Completed",
                    "dataset": f"train={train_rows}, val={val_rows}, test={test_rows}",
                    "notes": f"Best model: {best.get('model', 'unknown')}",
                    "params": {
                        "best_model": best.get("model", ""),
                        "best_family": best.get("family", ""),
                        "test_rows": int(_as_float(str(best.get("test_rows", 0)))),
                    },
                },
            }
        )
    return results
