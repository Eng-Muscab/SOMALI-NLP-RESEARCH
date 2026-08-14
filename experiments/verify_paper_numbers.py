"""Audit every model number printed in the paper against the artifacts on disk.

Why this exists
---------------
The published Experiment 1 numbers were once carried by hand from a stale
`step9_metrics.csv` (measured on an older 1,727-row test split) into the paper,
the README and the web app. That silently changed the reported champion. Numbers
that are typed by a human, or copied from an intermediate summary file, cannot be
trusted; numbers recomputed from `classification_report_*.csv` can.

This script is the single source of truth. It:

1. Recomputes every metric from each model's `classification_report_*.csv` and
   its `roc_curve_*.csv` -- never from a summary CSV.
2. Fails on integrity problems that would silently corrupt the paper:
     * a report whose support total != the real `clean_test.csv` row count
       (i.e. the model was evaluated on a different split);
     * a `roc_curve_*.csv` written more than ROC_SKEW_TOLERANCE from its report
       (i.e. accuracy and ROC-AUC describe different fits);
     * a model that has no report at all.
3. Scans the paper/README markdown for metric-shaped numbers on lines that name a
   model, and flags any that match no true value for that model.

Exit code is non-zero if anything fails, so this can gate a commit.

    python -m experiments.verify_paper_numbers            # audit
    python -m experiments.verify_paper_numbers --table    # print canonical table
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

EXPERIMENTS = {
    "experiment_1_stopwords_included": "Exp 1 (Stopwords Inc)",
    "experiment_2_stopwords_removed": "Exp 2 (Stopwords Rem)",
}

# A report and its ROC curve should be written by the same fit, seconds apart.
# Allow a couple of minutes for slow model saves between the two writes.
ROC_SKEW_TOLERANCE = timedelta(minutes=5)

DOCS_TO_AUDIT = [
    Path("paper/chapter_5_results_and_discussion.md"),
    Path("paper/research_paper.md"),
    Path("README.md"),
]

# Every surface that publishes model numbers must show all 26 rows (13 x 2).
# A row silently dropped here is as damaging as a wrong number.
COVERAGE_TARGETS = [
    Path("paper/chapter_5_results_and_discussion.md"),
    Path("README.md"),
    Path("web/frontend/src/pages/public/LandingPage.tsx"),
    Path("paper/render_saved_svgs_and_build_docx.py"),
    Path("paper/build_chapter5_word_doc.py"),
]

FAMILY_BY_MODEL = {
    "LogisticRegression_TFIDF": "Traditional ML",
    "LinearSVC_TFIDF": "Traditional ML",
    "RandomForest_TFIDF": "Traditional ML",
    "XGBoost_TFIDF": "Traditional ML",
    "BiLSTM_Keras": "Deep Learning",
    "BiLSTM_Word2Vec": "Deep Learning",
    "BiLSTM_FastText": "Deep Learning",
    "MiniTransformer_Keras": "Transformer",
    "XLMRoberta_FineTuned": "Transformer",
    "mBERT_FineTuned": "Transformer",
    "SomBERTa_FineTuned": "Transformer",
    "AfriBERTa_FineTuned": "Transformer",
    "AfroXLMR_FineTuned": "Transformer",
}


class Problem(Exception):
    pass


def load_truth() -> tuple[dict[tuple[str, str], dict], list[str]]:
    """Recompute every metric from the per-model reports. Returns (truth, errors)."""
    truth: dict[tuple[str, str], dict] = {}
    errors: list[str] = []

    for exp in EXPERIMENTS:
        exp_dir = ROOT / "experiments" / exp
        reports_dir = exp_dir / "evaluation" / "reports"
        test_path = exp_dir / "data" / "clean_test.csv"
        if not test_path.exists():
            errors.append(f"{exp}: missing {test_path.relative_to(ROOT)}")
            continue
        expected_rows = len(pd.read_csv(test_path, keep_default_na=False))

        for report_path in sorted(reports_dir.glob("classification_report_*.csv")):
            model = report_path.stem.replace("classification_report_", "")
            df = pd.read_csv(report_path).set_index("label")

            support = float(df.loc["weighted avg", "support"])
            if int(round(support)) != expected_rows:
                errors.append(
                    f"{exp}/{model}: evaluated on {int(support)} rows but "
                    f"clean_test.csv has {expected_rows} -- WRONG SPLIT"
                )

            roc_auc = None
            roc_path = reports_dir / f"roc_curve_{model}.csv"
            if roc_path.exists():
                curve = pd.read_csv(roc_path)
                if {"fpr", "tpr"}.issubset(curve.columns):
                    roc_auc = float(np.trapezoid(curve["tpr"], curve["fpr"]))
                skew = abs(
                    pd.Timestamp(report_path.stat().st_mtime, unit="s")
                    - pd.Timestamp(roc_path.stat().st_mtime, unit="s")
                )
                if skew > ROC_SKEW_TOLERANCE:
                    errors.append(
                        f"{exp}/{model}: roc_curve is {skew} away from the "
                        f"classification report -- accuracy and ROC-AUC describe "
                        f"DIFFERENT FITS"
                    )
            else:
                errors.append(f"{exp}/{model}: no roc_curve_{model}.csv, ROC-AUC unavailable")

            truth[(exp, model)] = {
                "accuracy": float(df.loc["accuracy", "f1-score"]),
                "precision": float(df.loc["weighted avg", "precision"]),
                "recall": float(df.loc["weighted avg", "recall"]),
                "f1": float(df.loc["weighted avg", "f1-score"]),
                "macro_f1": float(df.loc["macro avg", "f1-score"]),
                "roc_auc": roc_auc,
                "test_rows": int(round(support)),
            }

    # Training-set accuracy lives in its own file because it is scored separately, but
    # it is published in the same tables -- without it here the audit rejects every
    # train figure in the paper as "no such metric".
    for exp in EXPERIMENTS:
        path = ROOT / "experiments" / exp / "evaluation" / "reports" / "train_accuracy.csv"
        if not path.exists():
            continue
        for row in pd.read_csv(path).itertuples():
            entry = truth.get((exp, str(row.model)))
            if entry is not None:
                entry["train_accuracy"] = float(row.train_accuracy)

    missing = [
        f"{exp}/{model}"
        for exp in EXPERIMENTS
        for model in FAMILY_BY_MODEL
        if (exp, model) not in truth
    ]
    for item in missing:
        errors.append(f"{item}: NO REPORT -- model still missing from this experiment")

    return truth, errors


def champion(truth: dict[tuple[str, str], dict]) -> tuple[tuple[str, str], dict]:
    key = max(truth, key=lambda k: (truth[k]["accuracy"], truth[k]["f1"]))
    return key, truth[key]


def canonical_table(truth: dict[tuple[str, str], dict]) -> str:
    rows = sorted(truth.items(), key=lambda kv: -kv[1]["accuracy"])
    out = [
        "| Experiment | Model Family | Model Architecture | Accuracy | Precision | Recall | F1-Score | Macro-F1 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for (exp, model), m in rows:
        out.append(
            f"| {EXPERIMENTS[exp]} | {FAMILY_BY_MODEL.get(model, '?')} | {model} | "
            f"{m['accuracy']:.4f} | {m['precision']:.4f} | {m['recall']:.4f} | "
            f"{m['f1']:.4f} | {m['macro_f1']:.4f} |"
        )
    return "\n".join(out)


# Matches 0.9444 / .9444 / 94.44% / 94.90 -- the shapes a metric is printed in.
NUMBER_RE = re.compile(r"(?<![\w.])(\d{1,3}\.\d{1,4})\s*%?|(?<![\w.])(0\.\d{3,4})(?![\d])")

EXP1_HINTS = ("exp 1", "exp1", "stopwords inc", "stopwords included", "function words included")
EXP2_HINTS = ("exp 2", "exp2", "stopwords rem", "stopwords removed", "function words removed")


METRIC_KEYS = ("accuracy", "precision", "recall", "f1", "macro_f1", "roc_auc", "train_accuracy")

# Prose names models the way a reader would, not the way the artefacts key them.
DISPLAY_ALIASES = {
    "LinearSVC_TFIDF": ("LinearSVC",),
    "LogisticRegression_TFIDF": ("Logistic Regression",),
    "RandomForest_TFIDF": ("Random Forest",),
    "XGBoost_TFIDF": ("XGBoost",),
    "BiLSTM_Keras": ("BiLSTM (Keras)",),
    "SomBERTa_FineTuned": ("SomBERTa",),
    "AfriBERTa_FineTuned": ("AfriBERTa",),
    "AfroXLMR_FineTuned": ("AfroXLMR",),
    "XLMRoberta_FineTuned": ("XLM-RoBERTa", "XLM-R"),
    "mBERT_FineTuned": ("mBERT",),
}


def candidate_values(truth: dict, exps: list[str], model: str) -> set[float]:
    """Every value that could legitimately be printed for this model.

    Includes both scales (0.9444 and 94.44) and, because the ablation section
    reports drops like "-1.29 percentage points", the exp1-exp2 deltas too.
    """
    vals: set[float] = set()
    per_exp: dict[str, dict] = {}
    for exp in exps:
        m = truth.get((exp, model))
        if not m:
            continue
        per_exp[exp] = m
        for key in METRIC_KEYS:
            v = m.get(key)
            if v is None:
                continue
            vals.add(round(v, 4))          # 0.9444
            vals.add(round(v, 3))          # 0.944
            vals.add(round(v * 100, 2))    # 94.44
            vals.add(round(v * 100, 1))    # 94.4

    # Legitimate ablation deltas between the two experiments.
    e1 = per_exp.get("experiment_1_stopwords_included")
    e2 = per_exp.get("experiment_2_stopwords_removed")
    if e1 and e2:
        for key in METRIC_KEYS:
            a, b = e1.get(key), e2.get(key)
            if a is None or b is None:
                continue
            for d in (abs(a - b), abs(a - b) * 100):
                vals.add(round(d, 4))
                vals.add(round(d, 2))
                vals.add(round(d, 1))
    return vals


def audit_doc(path: Path, truth: dict) -> list[str]:
    problems: list[str] = []
    if not path.exists():
        return [f"{path}: missing"]

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        # Figure captions / the figure index carry figure numbers ("5.12"), file
        # paths and image links -- no metrics to audit.
        if "Figure" in line or "figures/" in line or line.lstrip().startswith("!["):
            continue

        models = [m for m in FAMILY_BY_MODEL if m in line]
        if not models:
            models = [m for m, names in DISPLAY_ALIASES.items()
                      if any(n in line for n in names)]
        if len(models) != 1:
            continue  # ambiguous or unrelated line
        model = models[0]

        low = line.lower()
        exps = []
        if any(h in low for h in EXP1_HINTS):
            exps.append("experiment_1_stopwords_included")
        if any(h in low for h in EXP2_HINTS):
            exps.append("experiment_2_stopwords_removed")
        if not exps:
            exps = list(EXPERIMENTS)  # row shows both experiments side by side

        allowed = candidate_values(truth, exps, model)
        if not allowed:
            continue

        bad: list[str] = []
        for match in NUMBER_RE.finditer(line):
            raw = match.group(1) or match.group(2)
            value = float(raw)
            # tolerate the last-digit rounding the docs use
            if not any(abs(value - a) < 0.006 for a in allowed):
                if raw not in bad:
                    bad.append(raw)
        if bad:
            expected = ", ".join(f"{v:.4f}" for v in sorted(x for x in allowed if x < 1.5))
            problems.append(
                f"{path.name}:{lineno}: {model}: printed {', '.join(bad)} "
                f"-- no such metric (true: {expected})"
            )
    return problems


def audit_coverage(path: Path, truth: dict) -> list[str]:
    """Every (experiment, model) pair must be represented, not just mentioned once.

    A results table lists each model twice -- once per experiment. Counting
    occurrences catches the common failure where only one experiment's row was
    updated and the other was silently dropped.
    """
    if not path.exists():
        return [f"{path}: missing"]

    text = path.read_text(encoding="utf-8")
    expected_pairs = len({k for k in truth})
    problems: list[str] = []

    missing: list[str] = []
    single: list[str] = []
    for model in FAMILY_BY_MODEL:
        pairs = [e for e in EXPERIMENTS if (e, model) in truth]
        if not pairs:
            continue
        count = text.count(model)
        if count == 0:
            missing.append(model)
        elif count < len(pairs):
            single.append(f"{model} (x{count}, needs {len(pairs)})")

    if missing:
        problems.append(f"{path.name}: MISSING ENTIRELY: {', '.join(missing)}")
    if single:
        problems.append(f"{path.name}: under-represented: {', '.join(single)}")
    if not problems:
        problems.append(f"OK {path.name}: all {expected_pairs} experiment/model rows present")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", action="store_true", help="print the canonical results table and exit")
    args = parser.parse_args()

    truth, integrity_errors = load_truth()
    if not truth:
        print("FATAL: no classification reports found at all")
        return 2

    if args.table:
        print(canonical_table(truth))
        return 0

    print(f"Loaded {len(truth)} model results from classification reports.\n")

    print("== INTEGRITY ==")
    if integrity_errors:
        for e in integrity_errors:
            print(f"  FAIL  {e}")
    else:
        print("  OK    every report matches its split and its ROC curve")
    print()

    (exp, model), best = champion(truth)
    print("== CHAMPION (recomputed, not copied) ==")
    print(f"  {model} / {EXPERIMENTS[exp]}")
    print(f"  accuracy={best['accuracy']:.4f}  f1={best['f1']:.4f}  "
          f"roc_auc={best['roc_auc']:.4f}" if best["roc_auc"] else
          f"  accuracy={best['accuracy']:.4f}  f1={best['f1']:.4f}  roc_auc=n/a")
    print()

    print(f"== COVERAGE (all {len(truth)} experiment/model rows on every surface) ==")
    coverage_problems: list[str] = []
    for rel in COVERAGE_TARGETS:
        for line in audit_coverage(ROOT / rel, truth):
            if line.startswith("OK "):
                print(f"  OK    {line[3:]}")
            else:
                print(f"  FAIL  {line}")
                coverage_problems.append(line)
    print()

    print("== VALUE AUDIT ==")
    doc_problems: list[str] = []
    for rel in DOCS_TO_AUDIT:
        doc_problems.extend(audit_doc(ROOT / rel, truth))
    if doc_problems:
        for p in doc_problems:
            print(f"  FAIL  {p}")
    else:
        print("  OK    every model number in the docs matches the artifacts")
    print()

    total = len(integrity_errors) + len(doc_problems) + len(coverage_problems)
    print(f"== RESULT: {'PASS' if total == 0 else f'{total} PROBLEM(S)'} ==")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
