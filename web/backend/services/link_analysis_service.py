"""Fetch a web article by URL and report how much of it reads as AI-generated.

The prediction page takes pasted text. This takes a link instead: it fetches the page,
strips the navigation, advertising and comment furniture, keeps the article body, and
then classifies the article as a whole and paragraph by paragraph, so the result can be
stated as a proportion -- "62% human, 38% AI" -- rather than a single verdict.

Two measured facts shape the design, both from `experiments/paragraph_accuracy.json`:

  * The classifier is 94.8% accurate on whole documents but only 79.4% on 30-word
    paragraphs, because it was trained on full articles. Short paragraphs are therefore
    excluded from the proportion rather than allowed to swing it.
  * Accuracy climbs with paragraph length (84.5% at 50 words, 92.0% at 120). The
    per-paragraph confidence reported to the caller is the measured accuracy for that
    paragraph's length band, not the model's raw margin, so the number on screen means
    what a reader will take it to mean.

The document-level verdict remains the headline, because it is the one measured at
94.8%; the proportion is offered as supporting detail.
"""

from __future__ import annotations

import html
import json
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; SomNLP-Research/1.0; +https://jamhuriya.edu.so)"
FETCH_TIMEOUT = 15
MAX_BYTES = 4_000_000

# Below this a paragraph carries too little evidence to score; measured accuracy at 30
# words is 79.4% against 94.8% for a whole document. Kept high deliberately: lowering it
# to admit short articles let weak 20-word paragraphs swing the proportion on long ones
# too. Short articles take the whole-article path below instead.
MIN_PARAGRAPH_WORDS = 40
# The shortest article the classifier can be asked about. Somali news sites routinely
# publish three-paragraph wire items, and refusing those made the page reject real
# articles; the document verdict works at this length, and the caveat says how well.
MIN_ARTICLE_WORDS = 30
# Below this the paragraph proportion is not worth reporting separately -- a two- or
# three-paragraph item gives at most three data points -- so the whole article is scored
# as a single segment instead of being split into ones too small to mean anything.
MIN_WORDS_FOR_PROPORTION = 120

_ACCURACY_PATH = Path(__file__).resolve().parents[3] / "experiments" / "paragraph_accuracy.json"

# Blocks that are never article text.
_STRIP_TAGS = re.compile(
    r"<(script|style|nav|header|footer|aside|form|noscript|figure|iframe|svg)\b[^>]*>.*?</\1>",
    re.I | re.S,
)
_STRIP_COMMENTS = re.compile(r"<!--.*?-->", re.S)
_PARAGRAPH = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)


class LinkFetchError(Exception):
    """The page could not be fetched or held no readable article."""


def _accuracy_tables() -> dict[str, dict[int, float]]:
    """Measured paragraph accuracy per model, used to report honest confidence.

    Held per model because the spread is large: at 30 words LinearSVC scores 79.4%
    while XGBoost scores 56.8%. Quoting one model's figure beside another's verdict
    would put a number on screen that describes the wrong classifier.
    """
    try:
        data = json.loads(_ACCURACY_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - absence must not break the endpoint
        logger.warning("paragraph_accuracy.json unavailable; per-paragraph confidence disabled")
        return {}
    tables = {}
    for name, stats in data.get("models", {}).items():
        tables[name.lower()] = {int(k.split()[0]): v["accuracy"] for k, v in stats["by_length"].items()}
    return tables


_ACCURACY = _accuracy_tables()

# Backend model keys are lower-case and use a different separator from the artefact
# names the measurement wrote.
_KEY_ALIASES = {
    "linear_svc_tfidf": "linearsvc_tfidf",
    "logistic_regression_tfidf": "logisticregression_tfidf",
    "random_forest_tfidf": "randomforest_tfidf",
}


def _table_for(model_key: str | None) -> dict[int, float]:
    if not _ACCURACY:
        return {}
    key = (model_key or "").lower()
    key = _KEY_ALIASES.get(key, key)
    for candidate, table in _ACCURACY.items():
        if key.endswith(candidate) or candidate in key:
            return table
    return {}


def accuracy_for(words: int, model_key: str | None = None) -> float | None:
    """Measured accuracy for a paragraph of this length under this model.

    Returns None when the model has no measured table, so the caller can say the
    accuracy is unknown rather than borrow a number from a different model.
    """
    table = _table_for(model_key)
    if not table:
        return None
    sizes = sorted(table)
    if words <= sizes[0]:
        return table[sizes[0]]
    if words >= sizes[-1]:
        return table[sizes[-1]]
    for low, high in zip(sizes, sizes[1:]):
        if low <= words <= high:
            span = high - low
            weight = (words - low) / span if span else 0.0
            return table[low] + weight * (table[high] - table[low])
    return table[sizes[-1]]


def _clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment))).strip()


def fetch(url: str) -> tuple[str, str, list[str]]:
    """Return (title, full_text, paragraphs) for the article at `url`."""
    if not re.match(r"^https?://", url, re.I):
        raise LinkFetchError("The address must start with http:// or https://")

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read(MAX_BYTES)
    except urllib.error.HTTPError as exc:
        raise LinkFetchError(f"The site returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LinkFetchError(f"Could not reach the page: {exc}") from exc

    document = raw.decode(charset, errors="replace")
    title = ""
    for pattern in (_H1, _TITLE):
        match = pattern.search(document)
        if match:
            title = _clean(match.group(1))
            if title:
                break

    body = _STRIP_COMMENTS.sub(" ", document)
    for _ in range(3):  # nested blocks need more than one pass
        body, count = _STRIP_TAGS.subn(" ", body)
        if not count:
            break

    paragraphs = [_clean(p) for p in _PARAGRAPH.findall(body)]
    paragraphs = [p for p in paragraphs if len(p.split()) >= 12]
    if not paragraphs:
        # Some sites do not use <p> at all; fall back to the whole stripped body.
        text = _clean(body)
        paragraphs = [c for c in re.split(r"(?<=[.!?])\s{2,}", text) if len(c.split()) >= 12]

    if not paragraphs:
        raise LinkFetchError("No readable article text was found on that page")

    return title, "\n\n".join(paragraphs), paragraphs


def analyse(paragraphs: list[str], predict_batch, model_key: str | None = None) -> dict:
    """Classify each long-enough paragraph and summarise the proportion.

    `predict_batch` takes a list of strings and returns a list of "AI"/"HUMAN"; it is
    injected so this module stays free of model-loading concerns, and it is a batch call
    because scoring paragraphs one at a time dominated the request time.

    Short articles are analysed rather than refused. When no paragraph clears the
    scoring floor the whole article is treated as one segment, so a three-paragraph wire
    item still returns a verdict instead of an error; `short_article` marks that case so
    the caller can say the proportion rests on the article as a whole.
    """
    keep = [(i, p, len(p.split())) for i, p in enumerate(paragraphs)]
    long_enough = [(i, p, w) for i, p, w in keep if w >= MIN_PARAGRAPH_WORDS]
    total_words = sum(w for _, _, w in keep)
    short_article = not long_enough or total_words < MIN_WORDS_FOR_PROPORTION

    if not long_enough and keep:
        # Every paragraph is below the floor. Scoring the joined text keeps the article
        # answerable; splitting it further would only produce segments with no measured
        # accuracy to report.
        joined = " ".join(p for _, p, _ in keep)
        verdict = (predict_batch([joined]) or [None])[0]
        return {
            "paragraphs_scored": 1 if verdict else 0,
            "paragraphs_skipped": 0,
            "ai_paragraphs": 1 if verdict == "AI" else 0,
            "human_paragraphs": 1 if verdict == "HUMAN" else 0,
            "ai_percent": 100.0 if verdict == "AI" else 0.0,
            "human_percent": 100.0 if verdict == "HUMAN" else 0.0,
            "ai_percent_by_words": 100.0 if verdict == "AI" else 0.0,
            "mean_paragraph_confidence": accuracy_for(total_words, model_key),
            "accuracy_measured": bool(_table_for(model_key)),
            "short_article": True,
            "segments": [
                {
                    "index": index,
                    "words": words,
                    "text": paragraph,
                    "verdict": verdict,
                    "scored": True,
                    "confidence": (lambda a: round(a, 4) if a is not None else None)(
                        accuracy_for(total_words, model_key)),
                }
                for index, paragraph, words in keep
            ],
        }

    skipped = len(keep) - len(long_enough)

    verdicts = predict_batch([p for _, p, _ in long_enough]) if long_enough else []
    labelled = {index: verdict for (index, _, _), verdict in zip(long_enough, verdicts)}

    # Every paragraph is returned, in document order and with its full text, so the page
    # can render the article as the reader would see it and colour it in place. Ones too
    # short to score carry verdict None rather than a guess.
    segments = [
        {
            "index": index,
            "words": words,
            "text": paragraph,
            "verdict": labelled.get(index),
            "scored": index in labelled,
            "confidence": (lambda a: round(a, 4) if a is not None else None)(
                accuracy_for(words, model_key)) if index in labelled else None,
        }
        for index, paragraph, words in keep
    ]
    scored = [s for s in segments if s["scored"]]

    total = len(scored)
    ai = sum(1 for s in scored if s["verdict"] == "AI")
    human = total - ai
    weighted = sum(s["words"] for s in scored if s["verdict"] == "AI")
    all_words = sum(s["words"] for s in scored) or 1

    return {
        "paragraphs_scored": total,
        "paragraphs_skipped": skipped,
        "ai_paragraphs": ai,
        "human_paragraphs": human,
        # Two proportions: by paragraph count, and weighted by length so a long AI
        # passage counts for more than a short one.
        "ai_percent": round(ai / total * 100, 1) if total else 0.0,
        "human_percent": round(human / total * 100, 1) if total else 0.0,
        "ai_percent_by_words": round(weighted / all_words * 100, 1),
        "mean_paragraph_confidence": (
            round(sum(s["confidence"] for s in scored) / total, 4)
            if total and all(s["confidence"] is not None for s in scored) else None
        ),
        "accuracy_measured": bool(_table_for(model_key)),
        "short_article": short_article,
        "segments": segments,
    }
