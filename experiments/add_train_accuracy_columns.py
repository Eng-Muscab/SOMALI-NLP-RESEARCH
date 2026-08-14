"""Add a Train Accuracy column to every model-comparison table.

The paper reported test accuracy alone, so a reader could not tell a model that
generalises from one that memorised -- RandomForest scores 100% on its own training
data and 87% on the test set, which is the single most informative number about it and
appeared nowhere.

Sources are `evaluation/reports/train_accuracy.csv` per experiment, written by
`experiments/compute_train_accuracy.py`. Every destination is located by an anchor in
the file, never by line or column number.

Run with Word CLOSED.

    python experiments/add_train_accuracy_columns.py [--dry-run]
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import docx  # noqa: E402

from experiments.verify_paper_numbers import FAMILY_BY_MODEL, load_truth  # noqa: E402

EXP1 = "experiment_1_stopwords_included"
EXP2 = "experiment_2_stopwords_removed"
DOCX = ROOT / "paper" / "research_paper.docx"
CHAPTER = ROOT / "paper" / "chapter_5_results_and_discussion.md"
PAPER_MD = ROOT / "paper" / "research_paper.md"
README = ROOT / "README.md"

DISPLAY = {
    "LogisticRegression_TFIDF": "Logistic Regression + TF-IDF",
    "LinearSVC_TFIDF": "LinearSVC + TF-IDF",
    "RandomForest_TFIDF": "Random Forest + TF-IDF",
    "XGBoost_TFIDF": "XGBoost + TF-IDF",
    "BiLSTM_Keras": "BiLSTM (Keras)",
    "BiLSTM_Word2Vec": "BiLSTM + Word2Vec",
    "BiLSTM_FastText": "BiLSTM + FastText",
    "MiniTransformer_Keras": "MiniTransformer (Keras)",
    "AfriBERTa_FineTuned": "AfriBERTa (fine-tuned)",
    "SomBERTa_FineTuned": "SomBERTa (fine-tuned)",
    "AfroXLMR_FineTuned": "AfroXLMR (fine-tuned)",
    "XLMRoberta_FineTuned": "XLM-RoBERTa (fine-tuned)",
    "mBERT_FineTuned": "mBERT (fine-tuned)",
}
changed: list[str] = []


def train_scores() -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for exp in (EXP1, EXP2):
        path = ROOT / "experiments" / exp / "evaluation" / "reports" / "train_accuracy.csv"
        if not path.exists():
            raise SystemExit(f"missing {path} - run experiments/compute_train_accuracy.py first")
        for row in pd.read_csv(path).itertuples():
            out[(exp, str(row.model))] = float(row.train_accuracy)
    return out


# ---------------------------------------------------------------- docx


def insert_docx_column(table, header: str, values: dict[str, str], after: str) -> int:
    """Insert a column of cells after the column whose header matches `after`.

    python-docx has no column insert, so each row's <w:tc> is deep-copied and the copy
    re-textualised -- that keeps the borders and shading the table already carries,
    which building a bare cell would lose.
    """
    headers = [c.text.strip() for c in table.rows[0].cells]
    if header in headers:
        return 0
    if after not in headers:
        raise LookupError(f"no {after!r} column in {headers}")
    at = headers.index(after)

    grid = table._tbl.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tblGrid"
    )
    if grid is not None and len(grid) > at:
        grid.insert(at + 1, copy.deepcopy(grid[at]))

    written = 0
    for index, row in enumerate(table.rows):
        cells = row.cells
        template = cells[at]._tc
        clone = copy.deepcopy(template)
        template.addnext(clone)
        # Re-read: the row's cell list changed identity after the insert.
        target = row.cells[at + 1]
        text = header if index == 0 else values.get(cells[0].text.strip(), "n/a")
        paragraph = target.paragraphs[0]
        if paragraph.runs:
            paragraph.runs[0].text = text
            for run in paragraph.runs[1:]:
                run.text = ""
        else:
            paragraph.add_run(text)
        written += 1
    return written


def apply_docx(scores: dict, dry_run: bool) -> None:
    document = docx.Document(str(DOCX))
    # Table 5 carries both experiments; Tables 6-8 are per family, same shape.
    plan = [
        (4, "Exp 1 Train", EXP1, "Exp 1 Acc."),
        (4, "Exp 2 Train", EXP2, "Exp 2 Acc."),
        (5, "Exp 1 Train", EXP1, "Exp 1 Accuracy"),
        (5, "Exp 2 Train", EXP2, "Exp 2 Accuracy"),
        (6, "Exp 1 Train", EXP1, "Exp 1 Accuracy"),
        (6, "Exp 2 Train", EXP2, "Exp 2 Accuracy"),
        (7, "Exp 1 Train", EXP1, "Exp 1 Accuracy"),
        (7, "Exp 2 Train", EXP2, "Exp 2 Accuracy"),
    ]
    total = 0
    for index, header, exp, after in plan:
        table = document.tables[index]
        values = {
            DISPLAY[model]: f"{scores[(exp, model)] * 100:.2f}%"
            for model in DISPLAY
            if (exp, model) in scores
        }
        try:
            written = insert_docx_column(table, header, values, after)
        except LookupError as exc:
            print(f"  Table idx {index}: {exc}")
            continue
        if written:
            print(f"  Table idx {index}: added {header!r} after {after!r} ({written} cells)")
            total += written
    if not total:
        print("  docx already has the train columns")
        return
    changed.append("research_paper.docx")
    if not dry_run:
        document.save(str(DOCX))
        print(f"  saved {DOCX.name}")


# ---------------------------------------------------------------- markdown


def add_markdown_column(text: str, header_pattern: str, header: str, after: str,
                        value_for: dict[str, str]) -> str:
    """Insert a column into the markdown table whose header row matches."""
    lines = text.splitlines()
    rx = re.compile(header_pattern)
    for i, line in enumerate(lines):
        if not rx.match(line):
            continue
        headers = [c.strip() for c in line.strip().strip("|").split("|")]
        if header in headers:
            return text
        if after not in headers:
            raise LookupError(f"no {after!r} column in {headers}")
        at = headers.index(after)

        end = i
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        rebuilt = []
        for offset, row in enumerate(lines[i:end]):
            cells = [c for c in row.strip().strip("|").split("|")]
            if offset == 0:
                cells.insert(at + 1, f" {header} ")
            elif offset == 1:
                cells.insert(at + 1, "---:")
            else:
                key = cells[0].strip().strip("*").strip("`")
                cells.insert(at + 1, f" {value_for.get(key, 'n/a')} ")
            rebuilt.append("|" + "|".join(cells) + "|")
        return "\n".join(lines[:i] + rebuilt + lines[end:]) + ("\n" if text.endswith("\n") else "")
    raise LookupError(header_pattern)


def apply_markdown(scores: dict, dry_run: bool) -> None:
    truth, _ = load_truth()

    def by_model(exp: str, fmt: str = "{:.2f}%") -> dict[str, str]:
        out = {}
        for model in FAMILY_BY_MODEL:
            if (exp, model) in scores:
                out[model] = fmt.format(scores[(exp, model)] * 100)
                out[f"**{model}**"] = out[model]
        return out

    # chapter 5: one row per experiment/model, so the column follows that row's experiment.
    text = CHAPTER.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("| Experiment | Model Family |"):
            continue
        headers = [c.strip() for c in line.strip().strip("|").split("|")]
        if "Train Acc" in headers:
            break
        at = headers.index("Accuracy")
        end = i
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        rebuilt = []
        for offset, row in enumerate(lines[i:end]):
            cells = row.strip().strip("|").split("|")
            if offset == 0:
                cells.insert(at, " Train Acc ")
            elif offset == 1:
                cells.insert(at, "---:")
            else:
                exp = EXP1 if "Inc" in cells[0] else EXP2
                model = cells[2].strip().strip("*")
                value = scores.get((exp, model))
                cells.insert(at, f" {value:.4f} " if value else " n/a ")
            rebuilt.append("|" + "|".join(cells) + "|")
        text = "\n".join(lines[:i] + rebuilt + lines[end:]) + "\n"
        changed.append("chapter_5_results_and_discussion.md")
        print("  chapter 5: added 'Train Acc' column")
        break
    else:
        print("  chapter 5: table not found")
    if not dry_run and "chapter_5_results_and_discussion.md" in changed:
        CHAPTER.write_text(text, encoding="utf-8")

    # research_paper.md: both experiments side by side on one row.
    text = PAPER_MD.read_text(encoding="utf-8")
    before = text
    for header, exp, after in [("Exp 1 Train", EXP1, "Exp 1 Acc"), ("Exp 2 Train", EXP2, "Exp 2 Acc")]:
        try:
            text = add_markdown_column(text, r"^\| Model \| Family \| Exp 1 Acc", header, after, by_model(exp))
        except LookupError as exc:
            print(f"  research_paper.md: {exc}")
    if text != before:
        changed.append("research_paper.md")
        print("  research_paper.md: added train columns")
        if not dry_run:
            PAPER_MD.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    scores = train_scores()
    print(f"{len(scores)} train scores loaded\n")
    print("docx:")
    apply_docx(scores, args.dry_run)
    print("markdown:")
    apply_markdown(scores, args.dry_run)

    print(f"\n{len(changed)} file(s) {'would change' if args.dry_run else 'changed'}: {', '.join(changed) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
