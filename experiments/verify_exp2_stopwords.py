"""Prove that every one of the 253 Somali function words is absent from Experiment 2.

Checks all five places Experiment 2 vocabulary is exposed:

  1. the train/val/test splits under experiment_2_stopwords_removed/data/
  2. the Experiment 2 EDA figures (top-20 words)
  3. the Experiment 2 paper figures (word clouds + top-20)
  4. the live web-platform endpoints (`/dataset/top-words` exp2, `/dataset/wordcloud`)
  5. the images actually embedded in paper/research_paper.docx

Stage 5 exists because stages 3 and 4 once passed while the submitted document
still showed the old clouds: Word stores these figures as a PNG plus an SVG
vector layer and renders the SVG, and a refresh had replaced only the PNGs.

Run:  python experiments/verify_exp2_stopwords.py
Exit code 0 = clean, 1 = at least one stop word leaked through.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.somali_stopwords import SOMALI_FUNCTION_WORDS, STOPWORD_COUNT

EXP2_DATA = ROOT / "experiments" / "experiment_2_stopwords_removed" / "data"
EXP2_EDA = ROOT / "experiments" / "experiment_2_stopwords_removed" / "eda" / "figures"
PAPER_FIGS = ROOT / "paper" / "paper_figures"
RESEARCH_DOCX = ROOT / "paper" / "research_paper.docx"

TOKEN_RE = re.compile(r"\b\w+\b")
# wordcloud writes literal <text>word</text>; matplotlib renders glyphs as <use>
# refs and leaves the readable label in an XML comment above the group.
SVG_TEXT_RE = re.compile(r">([^<>]+)</text>")
SVG_COMMENT_RE = re.compile(r"<!--\s*([^<>-]+?)\s*-->")

failures: list[str] = []


def svg_words_in(svg: str) -> list[str]:
    words = SVG_TEXT_RE.findall(svg) + SVG_COMMENT_RE.findall(svg)
    return [w.strip().lower() for w in words if w.strip()]


def svg_words(path: Path) -> list[str]:
    return svg_words_in(path.read_text(encoding="utf-8", errors="ignore"))


def report(name: str, leaked: list[str]) -> None:
    if leaked:
        failures.append(name)
        preview = ", ".join(sorted(set(leaked))[:12])
        print(f"  FAIL  {name}: {len(set(leaked))} stop words -> {preview}")
    else:
        print(f"  ok    {name}")


def check_splits() -> None:
    import pandas as pd

    print("\n[1/5] Experiment 2 data splits")
    for name in ("clean_train", "clean_val", "clean_test", "train", "val", "test"):
        path = EXP2_DATA / f"{name}.csv"
        if not path.exists():
            print(f"  skip  {path.name} (missing)")
            continue
        df = pd.read_csv(path).fillna("")
        column = "Text" if "Text" in df.columns else df.columns[0]
        leaked = Counter()
        for text in df[column].astype(str):
            leaked.update(w for w in TOKEN_RE.findall(text.lower()) if w in SOMALI_FUNCTION_WORDS)
        report(f"{path.name} ({len(df):,} rows)", list(leaked))


def check_svgs(label: str, paths: list[Path]) -> None:
    print(f"\n{label}")
    for path in paths:
        if not path.exists():
            print(f"  skip  {path.name} (missing)")
            continue
        words = svg_words(path)
        if not words:
            failures.append(f"{path.name} (unreadable)")
            print(f"  FAIL  {path.name}: no words could be extracted - check cannot vouch for it")
            continue
        leaked = [w for w in words if w in SOMALI_FUNCTION_WORDS]
        report(f"{path.name} ({len(words)} words)", leaked)


def check_platform() -> None:
    import asyncio

    print("\n[4/5] Web platform endpoints")
    try:
        from web.backend.controllers import experiments_controller as ec
    except Exception as exc:  # backend deps not installed in this env
        print(f"  skip  backend import failed: {exc}")
        return

    if len(ec.SOMALI_STOPWORDS) != STOPWORD_COUNT:
        failures.append("backend stop-word list")
        print(
            f"  FAIL  backend list has {len(ec.SOMALI_STOPWORDS)} words, "
            f"expected {STOPWORD_COUNT}"
        )
    else:
        print(f"  ok    backend list is the canonical {STOPWORD_COUNT}-word list")

    top_words = asyncio.run(ec.get_dataset_top_words(limit=25))
    exp2 = [w["word"] for w in top_words["exp2"]]
    report("/dataset/top-words (exp2)", [w for w in exp2 if w in SOMALI_FUNCTION_WORDS])

    clouds = asyncio.run(ec.get_wordcloud(limit=80))
    for source, words in clouds.items():
        leaked = [w["word"] for w in words if w["word"] in SOMALI_FUNCTION_WORDS]
        report(f"/dataset/wordcloud [{source}]", leaked)


def check_docx() -> None:
    """Every Experiment 2 figure embedded in the submitted document, found by caption.

    The figures are located by walking the document's drawings in order and reading
    the caption that follows each one, so this keeps working if the document is
    rebuilt and the media parts are renumbered.
    """
    import zipfile

    print("\n[5/5] Figures embedded in research_paper.docx")
    if not RESEARCH_DOCX.exists():
        print(f"  skip  {RESEARCH_DOCX.name} (missing)")
        return

    with zipfile.ZipFile(RESEARCH_DOCX) as z:
        rels = dict(
            re.findall(
                r'Id="([^"]+)"[^>]*Target="(media/[^"]+)"',
                z.read("word/_rels/document.xml.rels").decode("utf-8", errors="ignore"),
            )
        )
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
        paragraphs = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)

        checked = 0
        for i, paragraph in enumerate(paragraphs):
            media = [rels[rid] for rid in re.findall(r'r:embed="([^"]+)"', paragraph) if rid in rels]
            if not media:
                continue
            caption = next(
                (
                    text
                    for text in (re.sub(r"<[^>]+>", "", p).strip() for p in paragraphs[i : i + 4])
                    if text.startswith("Figure")
                ),
                "",
            )
            if "Experiment 2" not in caption:
                continue
            label = caption.split(":")[0]
            # Word renders the SVG layer over the PNG, so the SVG is what a reader sees.
            for target in media:
                if not target.endswith(".svg"):
                    continue
                checked += 1
                words = svg_words_in(z.read(f"word/{target}").decode("utf-8", errors="ignore"))
                if not words:
                    failures.append(f"{label} ({target}, unreadable)")
                    print(f"  FAIL  {label}: no words could be extracted from {target}")
                    continue
                leaked = [w for w in words if w in SOMALI_FUNCTION_WORDS]
                report(f"{label} {target.split('/')[-1]} ({len(words)} words)", leaked)

        if not checked:
            failures.append("research_paper.docx (no Experiment 2 figures found)")
            print("  FAIL  no Experiment 2 figures found - the caption match is stale")


def main() -> int:
    print(f"Canonical Somali function-word list: {STOPWORD_COUNT} words")

    check_splits()
    check_svgs("[2/5] Experiment 2 EDA figures", [EXP2_EDA / "top20_words.svg"])
    check_svgs(
        "[3/5] Experiment 2 paper figures",
        [
            PAPER_FIGS / "eda_top20_words_exp2.svg",
            PAPER_FIGS / "fig_wordcloud_exp2.svg",
            PAPER_FIGS / "fig_wordcloud_ai_exp2.svg",
            PAPER_FIGS / "fig_wordcloud_human_exp2.svg",
        ],
    )
    check_platform()
    check_docx()

    print()
    if failures:
        print(f"RESULT: {len(failures)} artefact(s) still contain function words:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print(f"RESULT: clean - all {STOPWORD_COUNT} function words are absent from Experiment 2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
