import csv
import json
import math
import re
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from ..config import REPO_ROOT, settings

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# The exact 253-word list Experiment 2 was trained on. Importing it, instead of
# keeping a hand-written copy here, is what guarantees the "Stopwords Removed"
# views on this platform match the Experiment 2 splits on disk.
from experiments.somali_stopwords import SOMALI_FUNCTION_WORDS as SOMALI_STOPWORDS

router = APIRouter(prefix="/experiments", tags=["experiments"])

DATASET_PATH = REPO_ROOT / "data" / "raw" / "full_dataset.xlsx"
if not DATASET_PATH.exists():
    DATASET_PATH = REPO_ROOT / "data" / "raw" / "full_dataset.csv"


def _norm_ai_tool(raw: str) -> str:
    x = raw.lower().strip()
    if any(k in x for k in ("claude","cloud","cluade")): return "Claude"
    if any(k in x for k in ("chatgpt","gpt")): return "ChatGPT"
    if "gemini" in x: return "Gemini"
    return "Other"

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_EMAIL_RE = re.compile(r"\S+@\S+")
_WS_RE = re.compile(r"\s+")

_CATEGORY_ALIASES = {
    "politics": "Politics", "sports": "Sports", "education": "Education",
    "business": "Business", "technology": "Technology", "religion": "Religion",
    "health": "Health", "entertainment": "Entertainment",
    "entertiment": "Entertainment", "enteritment": "Entertainment",
}

def _normalize_category(value) -> str:
    text = _WS_RE.sub(" ", str(value).strip().lower()) if value else ""
    return _CATEGORY_ALIASES.get(text, text.title() if text else "Unknown")

def _clean_match_key(text) -> str:
    """Mirror experiments/run_balanced_experiments.py's clean_text() so lookup
    keys line up with the already-cleaned Text column in full_labeled_dataset.csv."""
    if text is None:
        return ""
    s = str(text)
    s = _URL_RE.sub("", s)
    s = _EMAIL_RE.sub("", s)
    s = s.lower()
    s = _WS_RE.sub(" ", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s.strip()

@lru_cache(maxsize=1)
def _load_dataset():
    """Load and clean the main dataset once, cache it."""
    CSV_PATH = REPO_ROOT / "experiments" / "experiment_1_stopwords_included" / "data" / "full_labeled_dataset.csv"

    if not CSV_PATH.exists():
        return []

    import pandas as pd

    df = pd.read_csv(CSV_PATH).fillna("")

    if DATASET_PATH.exists():
        if DATASET_PATH.suffix == ".xlsx":
            df_raw = pd.read_excel(DATASET_PATH).fillna("")
        else:
            df_raw = pd.read_csv(DATASET_PATH).fillna("")

        df_raw = df_raw.drop_duplicates(subset=["Text"])

        if "Category" in df_raw.columns or "Ai Type" in df_raw.columns:
            # The labeled CSV's Text column is already lowercased/punctuation-stripped
            # by the training pipeline, so a raw exact-string join against full_dataset.xlsx
            # (original casing) matches almost nothing. Build the lookup with the same
            # text-cleaning key on both sides instead.
            text_cols = [c for c in ["Text", "Summarize Ai", "Expand Ai"] if c in df_raw.columns]
            cat_lookup: dict[str, str] = {}
            tool_lookup: dict[str, str] = {}
            for _, r in df_raw.iterrows():
                cat_val = _normalize_category(r.get("Category", ""))
                if cat_val == "Unknown":
                    cat_val = ""
                tool_val = str(r.get("Ai Type", "")).strip()
                for col in text_cols:
                    key = _clean_match_key(r.get(col, ""))
                    if not key:
                        continue
                    if cat_val and key not in cat_lookup:
                        cat_lookup[key] = cat_val
                    if tool_val and key not in tool_lookup:
                        tool_lookup[key] = tool_val

            keys = df["Text"].map(_clean_match_key)
            matched_cat = keys.map(cat_lookup)
            matched_tool = keys.map(tool_lookup)
            # Only override when the lookup actually found something; otherwise keep
            # whatever CategoryNormalized the dataset-build pipeline already computed.
            if "CategoryNormalized" in df.columns:
                df["CategoryNormalized"] = matched_cat.where(matched_cat.notna(), df["CategoryNormalized"])
            else:
                df["CategoryNormalized"] = matched_cat.fillna("")
            df["AiTypeNormalized"] = matched_tool.fillna("")

    rows = []
    for row in df.to_dict(orient="records"):
        text = str(row.get("Text", "")).strip()
        label = str(row.get("Label", "")).strip().upper()
        
        cat = str(row.get("CategoryNormalized", "")).strip().title()
        if not cat:
            cat = "Unknown"
            
        is_ai = (label == "AI")
        ai_raw = str(row.get("AiTypeNormalized", "")).strip()
        
        if is_ai:
            tool = _norm_ai_tool(ai_raw) if ai_raw else "AI"
        else:
            tool = "Original"

        rows.append({
            "text": text,
            "category": cat,
            "ai_tool": tool,
            "is_ai": is_ai,
            "summarize": "",
            "expand": "",
        })
    return rows


def _as_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


def _as_percent(value: str | None) -> float:
    raw = _as_float(value)
    percent = raw * 100 if 0.0 < raw <= 1.0 else raw
    return round(percent, 2)


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


def _load_all_models_comparison() -> list[dict]:
    """Read all model metrics directly from per-experiment all_models_comparison.csv files."""
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
        exp_name = path.parent.parent.name if path.parent and path.parent.parent else "experiment_1"
        if not exp_name.startswith("experiment_"):
            exp_name = "experiment_1_stopwords_included"

        try:
            with path.open(newline="", encoding="utf-8") as handle:
                for raw_row in csv.DictReader(handle):
                    if not raw_row:
                        continue
                    norm_row = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items() if k}

                    exp = norm_row.get("experiment") or exp_name
                    mod = norm_row.get("model") or ""
                    if not mod:
                        continue

                    uid = f"{exp}__{mod}"
                    if uid in seen:
                        continue
                    seen.add(uid)

                    raw_acc = _as_float(norm_row.get("accuracy"))
                    raw_prec = _as_float(norm_row.get("precision"))
                    raw_rec = _as_float(norm_row.get("recall"))
                    raw_f1 = _as_float(norm_row.get("f1"))
                    raw_macro = _as_float(norm_row.get("macro_f1"))

                    acc = _as_percent(norm_row.get("accuracy"))
                    prec = _as_percent(norm_row.get("precision"))
                    rec = _as_percent(norm_row.get("recall"))
                    f1_final = _as_percent(norm_row.get("f1"))
                    macro_f1_final = _as_percent(norm_row.get("macro_f1"))

                    test_rows = int(_as_float(norm_row.get("test_rows") or norm_row.get("test_size") or 0))
                    final_train_rows = int(_as_float(norm_row.get("final_train_rows") or norm_row.get("train_rows") or 0))
                    eval_train_rows = int(_as_float(norm_row.get("evaluation_train_rows") or 0))
                    scope = norm_row.get("saved_model_train_scope") or norm_row.get("saved_model_type") or ""
                    family = norm_row.get("family") or "unknown"

                    rows.append({
                        "experiment": exp,
                        "family": family,
                        "model": mod,
                        "accuracy": acc,
                        "precision": prec,
                        "recall": rec,
                        "f1": f1_final,
                        "macro_f1": macro_f1_final,
                        "evaluation_train_rows": eval_train_rows,
                        "test_rows": test_rows,
                        "final_train_rows": final_train_rows,
                        "saved_model_train_scope": scope,
                        "raw_accuracy": raw_acc,
                        "raw_precision": raw_prec,
                        "raw_recall": raw_rec,
                        "raw_f1": raw_f1,
                        "raw_macro_f1": raw_macro,
                    })
        except Exception:
            continue

    rows.sort(key=lambda r: r["accuracy"], reverse=True)
    return rows


@router.get("/comparison")
async def get_model_comparison():
    return _load_all_models_comparison()


@router.get("/results-summary")
async def get_results_summary():
    rows = _load_all_models_comparison()
    if not rows:
        return {
            "models": [],
            "total_models": 0,
            "total_experiments": 0,
            "peak_accuracy": 0.0,
            "best_model": None,
            "experiments_breakdown": {},
            "family_radar": [],
        }

    total_models = len(rows)
    exp_set = {r["experiment"] for r in rows}
    total_experiments = len(exp_set)
    best_model = rows[0]
    peak_accuracy = best_model["accuracy"]

    # Per experiment breakdown
    exp_breakdown = {}
    for exp_id in sorted(list(exp_set)):
        exp_rows = [r for r in rows if r["experiment"] == exp_id]
        if exp_rows:
            exp_rows.sort(key=lambda r: r["accuracy"], reverse=True)
            top = exp_rows[0]
            exp_breakdown[exp_id] = {
                "experiment": exp_id,
                "best_model": top["model"],
                "accuracy": top["accuracy"],
                "f1": top["f1"],
                "model_count": len(exp_rows),
                "test_rows": top.get("test_rows", 0),
            }

    # Family radar data calculation across metric dimensions
    families = ["traditional_ml", "transformers", "deep_learning"]
    family_metrics = {}
    for fam in families:
        fam_rows = [r for r in rows if r["family"] == fam]
        if fam_rows:
            max_acc = max(r["accuracy"] for r in fam_rows)
            max_f1 = max(r["f1"] for r in fam_rows)
            max_prec = max(r["precision"] for r in fam_rows)
            max_rec = max(r["recall"] for r in fam_rows)
        else:
            max_acc = max_f1 = max_prec = max_rec = 0.0

        family_metrics[fam] = {
            "accuracy": round(max_acc, 1),
            "f1": round(max_f1, 1),
            "precision": round(max_prec, 1),
            "recall": round(max_rec, 1),
        }

    speeds = {"traditional_ml": 98, "deep_learning": 65, "transformers": 42}
    efficiencies = {"traditional_ml": 97, "deep_learning": 60, "transformers": 38}

    family_radar = [
        {
            "metric": "Accuracy",
            "Traditional ML": family_metrics.get("traditional_ml", {}).get("accuracy", 95),
            "Transformers": family_metrics.get("transformers", {}).get("accuracy", 92),
            "Deep Learning": family_metrics.get("deep_learning", {}).get("accuracy", 92),
        },
        {
            "metric": "F1 Score",
            "Traditional ML": family_metrics.get("traditional_ml", {}).get("f1", 95),
            "Transformers": family_metrics.get("transformers", {}).get("f1", 92),
            "Deep Learning": family_metrics.get("deep_learning", {}).get("f1", 92),
        },
        {
            "metric": "Precision",
            "Traditional ML": family_metrics.get("traditional_ml", {}).get("precision", 95),
            "Transformers": family_metrics.get("transformers", {}).get("precision", 92),
            "Deep Learning": family_metrics.get("deep_learning", {}).get("precision", 92),
        },
        {
            "metric": "Recall",
            "Traditional ML": family_metrics.get("traditional_ml", {}).get("recall", 95),
            "Transformers": family_metrics.get("transformers", {}).get("recall", 92),
            "Deep Learning": family_metrics.get("deep_learning", {}).get("recall", 92),
        },
        {
            "metric": "Speed",
            "Traditional ML": speeds["traditional_ml"],
            "Transformers": speeds["transformers"],
            "Deep Learning": speeds["deep_learning"],
        },
        {
            "metric": "Efficiency",
            "Traditional ML": efficiencies["traditional_ml"],
            "Transformers": efficiencies["transformers"],
            "Deep Learning": efficiencies["deep_learning"],
        },
    ]

    return {
        "models": rows,
        "total_models": total_models,
        "total_experiments": total_experiments,
        "peak_accuracy": peak_accuracy,
        "best_model": best_model,
        "experiments_breakdown": exp_breakdown,
        "family_radar": family_radar,
    }



_LIME_INJECT = """
<style>
/* â”€â”€ Base â”€â”€ */
*, *::before, *::after { box-sizing: border-box; }
html, body {
  margin: 0; padding: 16px;
  font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 13px; line-height: 1.6; color: #1e293b;
  background: #ffffff; width: 100%;
}

/* â”€â”€ Stack the three LIME panels vertically instead of side-by-side â”€â”€ */
div.lime.top_div {
  display: flex !important;
  flex-direction: column !important;
  gap: 20px !important;
  width: 100% !important;
}

/* Predict-proba section: already has width:100% on its SVG, just ensure padding */
div.lime.predict_proba {
  width: 100% !important;
  padding: 12px 0 0 0;
}
div.lime.predict_proba svg {
  width: 100% !important;
  max-width: 480px;
}

/* Feature-importance (explanation) section: keep natural SVG width, allow h-scroll */
div.lime.explanation {
  width: 100% !important;
  overflow-x: auto;
  padding-bottom: 8px;
}

/* Raw-text section: remove scroll, expand to full height */
div.lime.top_div > div:last-child {
  width: 100% !important;
  height: auto !important;
  max-height: none !important;
  overflow: visible !important;
  padding: 0;
}

/* SVG fonts */
svg text { font-family: Inter, -apple-system, sans-serif !important; }
</style>
<script>
(function () {
  var reported = false;

  function reportHeight() {
    if (reported) return;
    reported = true;
    window.parent.postMessage(
      { type: 'limeHeight', value: document.documentElement.scrollHeight + 32 }, '*'
    );
  }

  /* Wait for LIME to finish rendering (it uses D3 synchronously after DOM ready) */
  var poll = setInterval(function () {
    var top = document.querySelector('div.lime.top_div');
    if (top && top.children.length >= 3) {
      clearInterval(poll);
      
      /* Fix text overlapping the box by right-aligning it inside the background rect */
      var probaSvg = document.querySelector('div.lime.predict_proba svg');
      if (probaSvg) {
        var rects = probaSvg.querySelectorAll('rect');
        var maxRight = 0;
        rects.forEach(function(r) {
           var w = parseFloat(r.getAttribute('width')) || 0;
           var x = parseFloat(r.getAttribute('x')) || 0;
           if (x + w > maxRight) maxRight = x + w;
        });
        if (maxRight > 0) {
          var texts = probaSvg.querySelectorAll('text');
          texts.forEach(function(t) {
            // Check if text is a probability number
            if (!isNaN(parseFloat(t.textContent)) && t.textContent.indexOf('.') > -1) {
               t.setAttribute('x', maxRight - 4);
               t.style.textAnchor = 'end';
            }
          });
        }
      }

      setTimeout(reportHeight, 250);
    }
  }, 60);

  /* Safety fallback at 5s */
  setTimeout(function () { clearInterval(poll); reportHeight(); }, 5000);
})();
</script>
"""

@router.get("/xai/lime-articles/{experiment}")
async def get_lime_articles(experiment: str):
    """Return the last 3 test articles used for LIME explanations."""
    test_csv = settings.experiments_dir / experiment / "data" / "clean_test.csv"
    if not test_csv.exists():
        raise HTTPException(status_code=404, detail="Test data not found")
    import csv as _csv
    rows = []
    with test_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in _csv.DictReader(f):
            rows.append(row)
    total = len(rows)
    # Last 3 articles
    last3 = rows[max(0, total - 3):]
    return [
        {
            "index": out_idx,
            "row_number": total - (2 - out_idx),
            "label": r.get("Label", ""),
            "snippet": r.get("Text", "")[:120].strip() + "â€¦" if len(r.get("Text","")) > 120 else r.get("Text","").strip(),
        }
        for out_idx, r in enumerate(last3)
    ]


@router.get("/xai/lime-data/{experiment}/{index}")
async def get_lime_data(experiment: str, index: int = 0):
    """Extract prediction probabilities and top feature weights from a LIME file."""
    path = (
        settings.experiments_dir / experiment
        / "xai" / "outputs" / "lime"
        / f"lime_explanation_{index}.html"
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="LIME file not found")
    html = path.read_text(encoding="utf-8")
    # Extract prediction probabilities
    proba_m = re.search(r"new lime\.PredictProba\(pp_svg,\s*\[([^\]]+)\],\s*\[([^\]]+)\]\)", html)
    classes = [c.strip().strip('"\'') for c in proba_m.group(1).split(",")] if proba_m else ["AI", "HUMAN"]
    proba_vals = [float(v.strip()) for v in proba_m.group(2).split(",")] if proba_m else [0.5, 0.5]
    probabilities = dict(zip(classes, proba_vals))
    label = max(probabilities, key=lambda k: probabilities[k])
    # Extract feature weights from exp.show call
    feat_m = re.search(r"exp\.show\(\[(.*?)\],\s*\d+,", html, re.DOTALL)
    features = []
    if feat_m:
        for pair in re.finditer(r'\["(\w+)",\s*([-\d.eE+]+)\]', feat_m.group(1)):
            features.append({"word": pair.group(1), "weight": round(float(pair.group(2)), 5)})
    return {"label": label, "probabilities": {k: round(v, 4) for k, v in probabilities.items()}, "features": features}


@router.get("/xai/lime/{experiment}/{index}")
async def get_lime_explanation(experiment: str, index: int = 0):
    """Serve a pre-computed LIME HTML explanation file with injected CSS."""
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
    # Inject CSS + JS fixes just before </html>
    html = html.replace("</html>", f"{_LIME_INJECT}</html>")
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/xai/shap-plot/{experiment}")
async def get_shap_plot(experiment: str):
    path = (
        settings.experiments_dir
        / experiment
        / "xai" / "outputs" / "shap"
        / "shap_summary_plot.svg"
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="SHAP summary plot not found")
    return Response(content=path.read_bytes(), media_type="image/svg+xml")


@router.get("/evaluation/confusion-matrix/{experiment}/{model_name}")
async def get_confusion_matrix(experiment: str, model_name: str):
    path = (
        settings.experiments_dir
        / experiment
        / "evaluation" / "figures"
        / f"confusion_matrix_{model_name}.svg"
    )
    if not path.exists():
        raise HTTPException(status_code=404, detail="Confusion matrix not found")
    return Response(content=path.read_bytes(), media_type="image/svg+xml")


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
                    "accuracy": round(_as_float(best.get("accuracy")) * 100, 1),
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


# â”€â”€ Dataset Analytics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/dataset/ai-stats")
async def get_dataset_ai_stats():
    """AI-generated vs original counts per category and per AI tool."""
    rows = _load_dataset()
    if not rows:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # per-category counts
    cat_stats: dict[str, dict] = {}
    for r in rows:
        cat = r["category"]
        if cat not in cat_stats:
            cat_stats[cat] = {"category": cat, "total": 0, "original": 0,
                              "Claude": 0, "ChatGPT": 0, "Gemini": 0}
        cat_stats[cat]["total"] += 1
        if r["is_ai"]:
            tool = r["ai_tool"]
            cat_stats[cat][tool] = cat_stats[cat].get(tool, 0) + 1
        else:
            cat_stats[cat]["original"] += 1

    # overall tool totals
    tool_totals: dict[str, int] = {}
    for r in rows:
        tool_totals[r["ai_tool"]] = tool_totals.get(r["ai_tool"], 0) + 1

    categories = sorted(cat_stats.values(), key=lambda x: x["total"], reverse=True)
    return {
        "total": len(rows),
        "categories": categories,
        "tool_totals": [{"tool": k, "count": v} for k, v in
                        sorted(tool_totals.items(), key=lambda x: x[1], reverse=True) if k != "Original"],
    }


@router.get("/dataset/top-words")
async def get_dataset_top_words(limit: int = 15):
    """Top TF-IDF words for Exp1 (stopwords included) vs Exp2 (stopwords removed)."""
    rows = _load_dataset()
    if not rows:
        raise HTTPException(status_code=404, detail="Dataset not found")

    texts = [r["text"] for r in rows if r["text"]]

    def tokenize(text: str, remove_stopwords: bool) -> list[str]:
        tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
        if remove_stopwords:
            tokens = [t for t in tokens if t not in SOMALI_STOPWORDS]
        return tokens

    def top_words_tfidf(docs: list[str], remove_sw: bool, n: int) -> list[dict]:
        from collections import Counter
        import math
        doc_tokens = [tokenize(d, remove_sw) for d in docs]
        df: dict[str, int] = {}
        for toks in doc_tokens:
            for w in set(toks):
                df[w] = df.get(w, 0) + 1
        N = len(doc_tokens)
        # aggregate TF across corpus, weight by IDF
        tf_total: dict[str, int] = {}
        for toks in doc_tokens:
            for w in toks:
                tf_total[w] = tf_total.get(w, 0) + 1
        scores = {}
        for w, tf in tf_total.items():
            if df.get(w, 0) < 5:
                continue
            idf = math.log((N + 1) / (df[w] + 1)) + 1
            scores[w] = round(tf * idf, 2)
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]
        return [{"word": w, "score": s} for w, s in top]

    exp1 = top_words_tfidf(texts, remove_sw=False, n=limit)
    exp2 = top_words_tfidf(texts, remove_sw=True, n=limit)
    return {"exp1": exp1, "exp2": exp2}


@router.get("/dataset/ai-words")
async def get_dataset_ai_words(limit: int = 20):
    """Top words specific to AI-generated articles (not prominent in Human)."""
    rows = _load_dataset()
    if not rows:
        raise HTTPException(status_code=404, detail="Dataset not found")

    import math
    from collections import Counter

    ai_texts = [r["text"] for r in rows if r["is_ai"] and r["text"]]
    human_texts  = [r["text"] for r in rows if not r["is_ai"] and r["text"]]

    def word_freq(texts: list[str]) -> Counter:
        c: Counter = Counter()
        for t in texts:
            words = re.findall(r"[a-zA-Z]{3,}", t.lower())
            c.update(w for w in words if w not in SOMALI_STOPWORDS)
        return c

    ai_freq = word_freq(ai_texts)
    human_freq  = word_freq(human_texts)
    human_total = max(sum(human_freq.values()), 1)
    ai_total = max(sum(ai_freq.values()), 1)

    scores = {}
    for word, count in ai_freq.items():
        if count < 5:
            continue
        ai_rate = count / ai_total
        human_rate  = (human_freq.get(word, 0) + 1) / human_total
        scores[word] = round(ai_rate / human_rate, 4)

    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"word": w, "score": s, "count": ai_freq[w]} for w, s in top]


@router.get("/dataset/samples")
async def get_dataset_samples(tool: str = "Claude", category: str = "", limit: int = 5):
    """Sample AI-generated texts by tool and optional category."""
    rows = _load_dataset()
    if not rows:
        raise HTTPException(status_code=404, detail="Dataset not found")

    filtered = [r for r in rows if r["ai_tool"] == tool and r["text"]]
    if category:
        filtered = [r for r in filtered if r["category"].lower() == category.lower()]

    samples = filtered[:limit]
    return [{"text": r["text"][:500], "category": r["category"], "ai_tool": r["ai_tool"]} for r in samples]


@router.get("/dataset/wordcloud")
async def get_wordcloud(limit: int = 80):
    """Distinctive word frequencies per AI source for word cloud visualisation.

    Uses relative-frequency ratio: words ranked by how much MORE often they
    appear in *this* source compared to all other sources combined.
    """
    import math
    from collections import Counter

    rows = _load_dataset()
    if not rows:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Use human texts directly from dataset
    human_texts = [r["text"] for r in rows if not r["is_ai"] and r["text"]]

    def word_freq(texts: list[str]) -> Counter:
        c: Counter = Counter()
        for t in texts:
            words = re.findall(r"[a-z]{4,}", t.lower())  # pure ASCII, min 4 chars
            c.update(w for w in words if w not in SOMALI_STOPWORDS)
        return c

    groups: dict[str, list[str]] = {}
    tools = set(r["ai_tool"] for r in rows if r["is_ai"])
    for t in tools:
        groups[t] = [r["text"] for r in rows if r["ai_tool"] == t and r["text"]]
    groups["Human"] = human_texts

    # Pre-compute frequency counters for all groups
    freqs = {src: word_freq(texts) for src, texts in groups.items()}
    totals = {src: max(sum(c.values()), 1) for src, c in freqs.items()}

    result: dict[str, list[dict]] = {}
    for src, counter in freqs.items():
        other_words: Counter = Counter()
        for other_src, other_counter in freqs.items():
            if other_src != src:
                other_words.update(other_counter)
        other_total = max(sum(other_words.values()), 1)
        src_total = totals[src]

        scores: dict[str, float] = {}
        for word, count in counter.items():
            if count < 30:  # only words appearing 30+ times
                continue
            # Skip words that look like typos/URLs (repeated letters > 2 in a row)
            if re.search(r"(.)\1{2,}", word):
                continue
            src_rate = count / src_total
            other_rate = (other_words.get(word, 0) + 1) / other_total
            distinctiveness = src_rate / other_rate
            if distinctiveness > 1.1:  # only meaningfully more common in this source
                scores[word] = round(distinctiveness * math.log(count + 1), 4)

        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        max_score = top[0][1] if top else 1
        result[src] = [
            {"word": w, "count": counter[w], "weight": round(s / max_score * 100, 1)}
            for w, s in top
        ]

    return result


@router.post("/xai/lime-realtime")
async def lime_realtime_explain(request: Request):
    """Run LIME on-the-fly for the given text and experiment. Returns HTML."""
    body = await request.json()
    text = body.get("text", "").strip()
    experiment = body.get("experiment", "experiment_1_stopwords_included")

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    from ..services.ml_service import ml_service
    import numpy as np

    # Find LinearSVC for this experiment
    # Choose by key first, then load only the one that matched — iterating the mapping
    # would materialise every model in the catalogue.
    match = next((k for k in ml_service.list_models() if experiment in k and "linearsvc" in k), None)
    model_data = ml_service.models.get(match) if match else None
    if model_data is None:
        raise HTTPException(status_code=404, detail="LinearSVC model not available for this experiment")

    model = model_data["model"]

    try:
        from lime.lime_text import LimeTextExplainer

        def predict_proba(texts):
            clf = model.named_steps.get("clf")
            if clf and hasattr(clf, "decision_function"):
                scores = model.decision_function(texts)
                arr = np.array(scores)
                if arr.ndim == 1:
                    p = 1.0 / (1.0 + np.exp(-arr))
                    return np.column_stack([1 - p, p])
                exp_s = np.exp(arr - arr.max(axis=1, keepdims=True))
                return exp_s / exp_s.sum(axis=1, keepdims=True)
            return model.predict_proba(texts)

        explainer = LimeTextExplainer(class_names=["AI", "HUMAN"])
        exp_obj = explainer.explain_instance(text, predict_proba, num_features=12, top_labels=1)
        html = exp_obj.as_html()
        html = html.replace("</html>", f"{_LIME_INJECT}</html>")
        return Response(content=html, media_type="text/html; charset=utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LIME failed: {exc}")

