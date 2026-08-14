"""Measure how well the champion model scores individual paragraphs, not whole articles.

The link-analysis page reports a proportion -- "62% human, 38% AI" -- by splitting an
article into paragraphs and classifying each one. The model was trained on whole
articles averaging a few hundred words, so its accuracy on a 30-word paragraph is a
different number, and one nobody had measured. Publishing a percentage without knowing
that number would put a figure on screen that looks precise and is not.

This splits every held-out test document into paragraphs, labels each with its parent
document's label, and scores them by length band. The output is what the UI should cite
as its confidence, and what the thesis should quote if the feature is described there.

    python experiments/measure_paragraph_accuracy.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXP1 = ROOT / "experiments" / "experiment_1_stopwords_included"
MODEL_DIR = EXP1 / "models" / "traditional_ml"
OUT = ROOT / "experiments" / "paragraph_accuracy.json"

# A paragraph shorter than this carries too little evidence to classify at all; the
# service will skip them rather than let them swing the proportion.
MIN_WORDS = 20
# Paragraph sizes a news page actually produces.
SIZES = [30, 50, 80, 120, 200]


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines, falling back to sentence groups for unbroken text."""
    parts = [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", str(text)) if p.strip()]
    if len(parts) > 1:
        return parts
    # Single block: group sentences into chunks of roughly paragraph size.
    sentences = re.split(r"(?<=[.!?])\s+", str(text).strip())
    chunks, current = [], []
    for sentence in sentences:
        current.append(sentence)
        if sum(len(s.split()) for s in current) >= 60:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return [c for c in chunks if c.strip()]


def measure(model, texts, labels, lengths, test) -> dict:
    predictions = model.predict(texts)
    if getattr(predictions, "dtype", None) is not None and predictions.dtype.kind in "iu":
        predictions = np.array(["AI", "HUMAN"])[predictions]
    correct = predictions == labels

    bands = {}
    for size in SIZES:
        mask = lengths == size
        if mask.any():
            bands[f"{size} words"] = {
                "chunks": int(mask.sum()),
                "accuracy": round(float(correct[mask].mean()), 4),
            }

    doc_pred = model.predict(test["Text"].astype(str).tolist())
    if getattr(doc_pred, "dtype", None) is not None and doc_pred.dtype.kind in "iu":
        doc_pred = np.array(["AI", "HUMAN"])[doc_pred]
    return {
        "paragraph_accuracy": round(float(correct.mean()), 4),
        "document_accuracy": round(float((doc_pred == test["Label"].to_numpy()).mean()), 4),
        "by_length": bands,
    }


def main() -> int:
    test = pd.read_csv(EXP1 / "data" / "clean_test.csv", keep_default_na=False)
    print(f"{len(test):,} test documents")

    # The corpus stores each article as one unbroken block, so splitting on blank lines
    # hands the whole document back and measures nothing new. Real web articles arrive
    # broken into paragraphs, so each document is cut at the sizes a page actually
    # produces and every size is scored separately.
    texts, labels, lengths = [], [], []
    for row in test.itertuples():
        words = str(row.Text).split()
        for size in SIZES:
            for start in range(0, len(words) - size + 1, size):
                texts.append(" ".join(words[start:start + size]))
                labels.append(row.Label)
                lengths.append(size)
    print(f"{len(texts):,} chunks across {len(SIZES)} paragraph sizes\n")

    labels = np.array(labels)
    lengths = np.array(lengths)

    # Every selectable model needs its own table: the page prints a per-paragraph
    # accuracy beside each label, and quoting one model's figure next to another
    # model's verdict would describe a model that did not produce it.
    results = {}
    header = f"{'model':<26}" + "".join(f"{s:>8}" for s in SIZES) + f"{'doc':>9}"
    print(header)
    print("-" * len(header))
    for path in sorted(MODEL_DIR.glob("*.joblib")):
        stats = measure(joblib.load(path), texts, labels, lengths, test)
        results[path.stem] = stats
        row = f"{path.stem:<26}"
        for size in SIZES:
            band = stats["by_length"].get(f"{size} words")
            row += f"{band['accuracy']:>8.1%}" if band else f"{'-':>8}"
        print(row + f"{stats['document_accuracy']:>9.1%}")

    OUT.write_text(json.dumps({
        "experiment": "experiment_1_stopwords_included",
        "min_words": MIN_WORDS,
        "chunks_evaluated": len(texts),
        "models": results,
        # Kept so callers that predate per-model tables keep working.
        "by_length": results.get("LinearSVC_TFIDF", {}).get("by_length", {}),
        "paragraph_accuracy": results.get("LinearSVC_TFIDF", {}).get("paragraph_accuracy"),
        "document_accuracy": results.get("LinearSVC_TFIDF", {}).get("document_accuracy"),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
