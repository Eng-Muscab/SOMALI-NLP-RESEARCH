import csv
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..config import REPO_ROOT, settings

router = APIRouter(prefix="/experiments", tags=["experiments"])

DATASET_CSV = REPO_ROOT / "data" / "raw" / "full_dataset.csv"

SOMALI_STOPWORDS = {
    "iyo","oo","ku","ka","la","in","uu","ay","si","aan","waa","u","ee","ah",
    "ama","kale","mid","soo","loo","lagu","ugu","waxaa","waxay","waxa","wax",
    "laga","inay","sida","kala","badan","aad","waxa","waxaana","inuu","lakin",
    "hase","yeeshee","sidaas","markaa","markaas","inkastoo","xataa","balse",
    "haddii","haddaad","marka","laakiin","dadka","dalka","magaalada","sannadka",
}

def _norm_ai_tool(raw: str) -> str:
    x = raw.lower().strip()
    if any(k in x for k in ("claude","cloud","cluade")): return "Claude"
    if any(k in x for k in ("chatgpt","gpt")): return "ChatGPT"
    if "gemini" in x: return "Gemini"
    return "Other"

@lru_cache(maxsize=1)
def _load_dataset():
    """Load and clean the main dataset once, cache it."""
    if not DATASET_CSV.exists():
        return []
    rows = []
    with DATASET_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cat = row.get("Category", "").strip().title()
            ai_raw = row.get("Ai Type", "").strip()
            tool = _norm_ai_tool(ai_raw) if ai_raw else "Original"
            rows.append({
                "text": row.get("Text", "").strip(),
                "category": cat,
                "ai_tool": tool,
                "is_ai": bool(ai_raw),
                "summarize": row.get("Summarize Ai", "").strip(),
                "expand": row.get("Expand Ai", "").strip(),
            })
    return rows


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


_LIME_INJECT = """
<style>
/* ── Base ── */
*, *::before, *::after { box-sizing: border-box; }
html, body {
  margin: 0; padding: 16px;
  font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 13px; line-height: 1.6; color: #1e293b;
  background: #ffffff; width: 100%;
}

/* ── Stack the three LIME panels vertically instead of side-by-side ── */
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
      setTimeout(reportHeight, 250);
    }
  }, 60);

  /* Safety fallback at 5s */
  setTimeout(function () { clearInterval(poll); reportHeight(); }, 5000);
})();
</script>
"""

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


# ── Dataset Analytics ──────────────────────────────────────────────────────────

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
        tokens = re.findall(r"[a-zA-ZaàáâäãåèéêëìíîïñòóôöùúûüÀ-ÖØ-öø-ÿ]{3,}", text.lower())
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


@router.get("/dataset/claude-words")
async def get_dataset_claude_words(limit: int = 20):
    """Top words specific to Claude-generated articles (not prominent in ChatGPT/Gemini)."""
    rows = _load_dataset()
    if not rows:
        raise HTTPException(status_code=404, detail="Dataset not found")

    import math
    from collections import Counter

    claude_texts = [r["text"] for r in rows if r["ai_tool"] == "Claude" and r["text"]]
    other_texts  = [r["text"] for r in rows if r["ai_tool"] != "Claude" and r["text"]]

    def word_freq(texts: list[str]) -> Counter:
        c: Counter = Counter()
        for t in texts:
            words = re.findall(r"[a-zA-ZÀ-ɏ]{3,}", t.lower())
            c.update(w for w in words if w not in SOMALI_STOPWORDS)
        return c

    claude_freq = word_freq(claude_texts)
    other_freq  = word_freq(other_texts)
    other_total = max(sum(other_freq.values()), 1)
    claude_total = max(sum(claude_freq.values()), 1)

    scores = {}
    for word, count in claude_freq.items():
        if count < 5:
            continue
        claude_rate = count / claude_total
        other_rate  = (other_freq.get(word, 0) + 1) / other_total
        scores[word] = round(claude_rate / other_rate, 4)

    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"word": w, "score": s, "count": claude_freq[w]} for w, s in top]


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

    # Load human texts from experiment data
    human_texts: list[str] = []
    exp_csv = settings.experiments_dir / "experiment_1_stopwords_included" / "data" / "full_labeled_dataset.csv"
    if exp_csv.exists():
        import csv as _csv
        with exp_csv.open(encoding="utf-8-sig") as f:
            for row in _csv.DictReader(f):
                if row.get("Label", "").strip().upper() == "HUMAN" and row.get("Text", "").strip():
                    human_texts.append(row["Text"].strip())

    def word_freq(texts: list[str]) -> Counter:
        c: Counter = Counter()
        for t in texts:
            words = re.findall(r"[a-zA-ZÀ-ɏ]{3,}", t.lower())
            c.update(w for w in words if w not in SOMALI_STOPWORDS)
        return c

    def word_freq(texts: list[str]) -> Counter:
        c: Counter = Counter()
        for t in texts:
            words = re.findall(r"[a-z]{4,}", t.lower())  # pure ASCII, min 4 chars
            c.update(w for w in words if w not in SOMALI_STOPWORDS)
        return c

    groups: dict[str, list[str]] = {
        "Claude":  [r["text"] for r in rows if r["ai_tool"] == "Claude"  and r["text"]],
        "ChatGPT": [r["text"] for r in rows if r["ai_tool"] == "ChatGPT" and r["text"]],
        "Gemini":  [r["text"] for r in rows if r["ai_tool"] == "Gemini"  and r["text"]],
        "Human":   human_texts,
    }

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
