"""Emit every results table, in the exact format each destination file expects.

Rationale
---------
The published Experiment 1 numbers were once wrong because a human (me) retyped
them from a stale summary CSV, which silently changed the reported champion.
Retyping is the failure mode. So nothing here is typed: every block below is
rendered from the same recomputed truth that `verify_paper_numbers.py` audits
against, and is meant to be pasted verbatim into its destination.

    python -m experiments.generate_paper_tables              # all blocks
    python -m experiments.generate_paper_tables --only landing

Destinations:
    chapter   paper/chapter_5_results_and_discussion.md   S5.2.2 table
    readme    README.md                                    results table
    paper     paper/research_paper.md                      side-by-side table
    landing   web/frontend/src/pages/public/LandingPage.tsx  DEFAULT_MODELS
    docx      paper/*.py                                    t2_data literal
    ablation  chapter + README                              S5.3.1 bullets
"""
from __future__ import annotations

import argparse
import sys

from experiments.verify_paper_numbers import (
    EXPERIMENTS,
    FAMILY_BY_MODEL,
    champion,
    load_truth,
)

EXP1 = "experiment_1_stopwords_included"
EXP2 = "experiment_2_stopwords_removed"

# Per-destination spellings of the same two facts.
EXP_LABEL_CHAPTER = {EXP1: "Exp 1 (Stopwords Inc)", EXP2: "Exp 2 (Stopwords Rem)"}
EXP_LABEL_README = {EXP1: "Stopwords included", EXP2: "Stopwords removed"}
EXP_LABEL_DOCX = {EXP1: "Exp 1 (Inc)", EXP2: "Exp 2 (Rem)"}
FAMILY_CODE = {"Traditional ML": "traditional_ml", "Deep Learning": "deep_learning", "Transformer": "transformers"}

# Models the ablation section discusses, in the order it discusses them.
ABLATION_MODELS = ["LinearSVC_TFIDF", "LogisticRegression_TFIDF", "XGBoost_TFIDF", "BiLSTM_Keras"]


def ranked(truth: dict) -> list:
    return sorted(truth.items(), key=lambda kv: (-kv[1]["accuracy"], -kv[1]["f1"]))


def block_chapter(truth: dict, best_key) -> str:
    out = [
        "| Experiment | Model Family | Model Architecture | Accuracy | Precision | Recall | F1-Score | Macro-F1 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for key, m in ranked(truth):
        exp, model = key
        cells = [
            EXP_LABEL_CHAPTER[exp],
            FAMILY_BY_MODEL[model],
            model,
            f"{m['accuracy']:.4f}",
            f"{m['precision']:.4f}",
            f"{m['recall']:.4f}",
            f"{m['f1']:.4f}",
            f"{m['macro_f1']:.4f}",
        ]
        if key == best_key:  # champion row is bolded
            cells = [f"**{c}**" for c in cells]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def block_readme(truth: dict, best_key) -> str:
    out = [
        "| Experiment | Family | Model | Accuracy | F1 |",
        "|---|---|---|---:|---:|",
    ]
    for key, m in ranked(truth):
        exp, model = key
        acc, f1 = f"{m['accuracy']:.4f}", f"{m['f1']:.4f}"
        if key == best_key:
            acc, f1 = f"**{acc}**", f"**{f1}**"
        out.append(f"| {EXP_LABEL_README[exp]} | {FAMILY_BY_MODEL[model]} | {model} | {acc} | {f1} |")
    return "\n".join(out)


def block_paper(truth: dict, best_key) -> str:
    """research_paper.md puts both experiments on one row, ranked by Exp 1."""
    out = [
        "| Model | Family | Exp 1 Acc | Exp 1 F1 | Exp 2 Acc | Exp 2 F1 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    models = sorted(
        FAMILY_BY_MODEL,
        key=lambda mo: -truth.get((EXP1, mo), {}).get("accuracy", 0.0),
    )
    for model in models:
        a, b = truth.get((EXP1, model)), truth.get((EXP2, model))
        if not a and not b:
            continue
        a1 = f"{a['accuracy'] * 100:.2f}%" if a else "n/a"
        f1a = f"{a['f1']:.3f}" if a else "n/a"
        a2 = f"{b['accuracy'] * 100:.2f}%" if b else "n/a"
        f1b = f"{b['f1']:.3f}" if b else "n/a"
        if best_key == (EXP1, model):
            a1, f1a = f"**{a1}**", f"**{f1a}**"
        out.append(f"| {model} | {FAMILY_BY_MODEL[model]} | {a1} | {f1a} | {a2} | {f1b} |")
    return "\n".join(out)


def block_landing(truth: dict) -> str:
    out = ["const DEFAULT_MODELS: ModelRow[] = ["]
    for (exp, model), m in ranked(truth):
        out.append(
            f"  {{ experiment: '{exp}', family: '{FAMILY_CODE[FAMILY_BY_MODEL[model]]}', "
            f"model: '{model}', accuracy: {m['accuracy'] * 100:.2f}, "
            f"precision: {m['precision'] * 100:.2f}, recall: {m['recall'] * 100:.2f}, "
            f"f1: {m['f1'] * 100:.2f}, macro_f1: {m['macro_f1'] * 100:.2f} }},"
        )
    out.append("]")
    return "\n".join(out)


def block_docx(truth: dict) -> str:
    out = ["    t2_data = ["]
    for (exp, model), m in ranked(truth):
        out.append(
            f'        ["{EXP_LABEL_DOCX[exp]}", "{FAMILY_BY_MODEL[model]}", "{model}", '
            f'"{m["accuracy"]:.4f}", "{m["precision"]:.4f}", "{m["recall"]:.4f}", '
            f'"{m["f1"]:.4f}", "{m["macro_f1"]:.4f}"],'
        )
    out.append("    ]")
    return "\n".join(out)


def block_ablation(truth: dict) -> str:
    out = []
    for model in ABLATION_MODELS:
        a, b = truth.get((EXP1, model)), truth.get((EXP2, model))
        if not a or not b:
            out.append(f"- `{model}`: MISSING from one experiment - cannot state a delta")
            continue
        drop = (a["accuracy"] - b["accuracy"]) * 100
        verb = "Dropped" if drop >= 0 else "Rose"
        out.append(
            f"- `{model}`: {verb} from **{a['accuracy'] * 100:.2f}%** (Stopwords Included) "
            f"to **{b['accuracy'] * 100:.2f}%** (Stopwords Removed), "
            f"a change of {abs(drop):.2f} percentage points."
        )
    return "\n".join(out)


BLOCKS = {
    "chapter": ("paper/chapter_5_results_and_discussion.md  S5.2.2 table", block_chapter),
    "readme": ("README.md  results table", block_readme),
    "paper": ("paper/research_paper.md  side-by-side table", block_paper),
    "landing": ("web/frontend/src/pages/public/LandingPage.tsx  DEFAULT_MODELS", block_landing),
    "docx": ("paper/*.py  t2_data literal", block_docx),
    "ablation": ("chapter S5.3.1 + README  ablation bullets", block_ablation),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=sorted(BLOCKS), help="emit a single block")
    args = parser.parse_args()

    truth, errors = load_truth()
    if not truth:
        print("FATAL: no classification reports found")
        return 2

    blocking = [e for e in errors if "NO REPORT" in e or "WRONG SPLIT" in e]
    if blocking:
        print("REFUSING TO GENERATE -- the artifacts are not trustworthy yet:\n")
        for e in blocking:
            print(f"  {e}")
        print("\nFix these first; a table built on them would be wrong.")
        return 1
    if errors:
        print("WARNING (not blocking, but ROC-AUC may describe a different fit):")
        for e in errors:
            print(f"  {e}")
        print()

    best_key, best = champion(truth)
    print(f"# {len(truth)} model results | champion: {best_key[1]} "
          f"({EXPERIMENTS[best_key[0]]}) acc={best['accuracy']:.4f}\n")

    wanted = [args.only] if args.only else list(BLOCKS)
    for name in wanted:
        desc, fn = BLOCKS[name]
        body = fn(truth, best_key) if fn in (block_chapter, block_readme, block_paper) else fn(truth)
        print(f"{'=' * 78}\n### {name} -> {desc}\n{'=' * 78}")
        print(body)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
