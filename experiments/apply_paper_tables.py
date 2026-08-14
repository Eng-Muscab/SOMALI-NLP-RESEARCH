"""Write the generated results tables into their destination files.

`generate_paper_tables.py` renders every table from recomputed truth but only prints
it -- the blocks still have to be pasted by hand, and hand-pasting is exactly how the
published numbers went stale the last three times.  This applies them.

Each destination is located by an anchor in the file itself, never by line number, so
the script keeps working when the surrounding prose is edited.  It also refreshes the
prose that quotes the stop-word list size, which changes whenever the list does.

    python experiments/apply_paper_tables.py [--dry-run] [--only chapter,landing]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.generate_paper_tables import (  # noqa: E402
    ABLATION_MODELS,
    block_ablation,
    block_chapter,
    block_landing,
    block_paper,
    block_readme,
)
from experiments.somali_stopwords import STOPWORD_COUNT  # noqa: E402
from experiments.verify_paper_numbers import champion, load_truth  # noqa: E402

EXP1 = "experiment_1_stopwords_included"
EXP2 = "experiment_2_stopwords_removed"

CHAPTER = ROOT / "paper" / "chapter_5_results_and_discussion.md"
README = ROOT / "README.md"
PAPER_MD = ROOT / "paper" / "research_paper.md"
LANDING = ROOT / "web" / "frontend" / "src" / "pages" / "public" / "LandingPage.tsx"

changed: list[str] = []


def replace_markdown_table(text: str, header_pattern: str, block: str) -> str:
    """Swap the table whose header matches, keeping everything around it."""
    lines = text.splitlines()
    rx = re.compile(header_pattern)
    for i, line in enumerate(lines):
        if not rx.match(line):
            continue
        end = i
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        return "\n".join(lines[:i] + block.splitlines() + lines[end:]) + ("\n" if text.endswith("\n") else "")
    raise LookupError(header_pattern)


def replace_bullets(text: str, block: str) -> str:
    """Swap the run of ablation bullets, which are one per model in a fixed order."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(r"^- `" + ABLATION_MODELS[0] + r"`:", line)]
    if not starts:
        raise LookupError("ablation bullets")
    i = starts[0]
    end = i
    while end < len(lines) and lines[end].startswith("- `"):
        end += 1
    return "\n".join(lines[:i] + block.splitlines() + lines[end:]) + ("\n" if text.endswith("\n") else "")


def write(path: Path, new: str, dry_run: bool) -> None:
    old = path.read_text(encoding="utf-8")
    if old == new:
        print(f"  ok    {path.relative_to(ROOT)} already current")
        return
    if not dry_run:
        path.write_text(new, encoding="utf-8")
    changed.append(str(path.relative_to(ROOT)))
    print(f"  {'would update' if dry_run else 'updated'}  {path.relative_to(ROOT)}")


def ablation_narrative(truth: dict) -> tuple[str, str, str]:
    """The three ablation claims, stated from the deltas rather than from memory.

    These sentences name which models moved and in which direction, so a list change
    can invert them outright -- with the 483-word list, SomBERTa and XLM-RoBERTa
    crossed from favouring Experiment 2 to favouring Experiment 1, which the previous
    hand-written paragraph still denied.
    """
    deltas = {
        model: (truth[(EXP1, model)]["accuracy"] - truth[(EXP2, model)]["accuracy"]) * 100
        for model in {m for e, m in truth if e == EXP1} & {m for e, m in truth if e == EXP2}
    }
    hurt = sorted(((d, m) for m, d in deltas.items() if d > 0), reverse=True)
    helped = sorted((d, m) for m, d in deltas.items() if d <= 0)

    lead = (
        f"**Keeping Somali function words yielded higher performance for {len(hurt)} of the "
        f"{len(deltas)} benchmarked models** — including every traditional-ML model and every "
        f"BiLSTM variant — when the {STOPWORD_COUNT}-word list is stripped:"
    )

    if helped:
        moved = ", ".join(
            f"`{m}` rises from {truth[(EXP1, m)]['accuracy'] * 100:.2f}% to "
            f"{truth[(EXP2, m)]['accuracy'] * 100:.2f}%"
            for _, m in helped
        )
        reverse = (
            f"The effect is not universal, and reporting it as such would overstate the result. "
            f"{len(helped)} of the {len(deltas)} models move the other way: {moved}. These are also "
            f"among the weakest models in the study. Under a single CPU-budgeted epoch with only the "
            f"final encoder block unfrozen, they never learn to exploit function-word distribution in "
            f"the first place, so discarding those tokens shortens the input without destroying signal "
            f"they were using. The finding is therefore that **function words carry discriminative "
            f"signal that well-fitted models exploit and under-fitted ones cannot**, rather than that "
            f"stopword removal is harmful in all circumstances."
        )
    else:
        reverse = (
            f"The effect is universal across the {len(deltas)} benchmarked models: not one scores "
            f"higher once the {STOPWORD_COUNT}-word list is removed."
        )

    svc, lr = deltas["LinearSVC_TFIDF"], deltas["LogisticRegression_TFIDF"]
    comparison = "more robust to" if svc < lr else "hurt more by"
    robust = (
        f"`LinearSVC_TFIDF` is also {comparison} the expanded list than "
        f"`LogisticRegression_TFIDF` ({-svc:.2f} pp against {-lr:.2f} pp) — its margin-maximising "
        f"objective responds differently to the loss of content-word features than logistic "
        f"regression's probabilistic one, and it remains the strongest model in both experiments."
    )
    return lead, reverse, robust


def margin_note(truth: dict) -> str:
    """The Experiment 2 margin between the top two sparse models, recomputed."""
    a = lambda e, m: truth[(e, m)]["accuracy"] * 100  # noqa: E731
    svc2, lr2 = a(EXP2, "LinearSVC_TFIDF"), a(EXP2, "LogisticRegression_TFIDF")
    svc1, lr1 = a(EXP1, "LinearSVC_TFIDF"), a(EXP1, "LogisticRegression_TFIDF")
    wider = "a wider margin than" if (svc2 - lr2) > (svc1 - lr1) else "a narrower margin than"
    return (
        f"Note: within Experiment 2 specifically, `LinearSVC_TFIDF` ({svc2:.2f}%) outperforms "
        f"`LogisticRegression_TFIDF` ({lr2:.2f}%) by {wider} it does in Experiment 1 "
        f"({svc1:.2f}% vs {lr1:.2f}%). The expanded {STOPWORD_COUNT}-word stopword list removes "
        f"common content words alongside function words, which affects LogisticRegression's "
        f"probabilistic objective more than LinearSVC's margin-maximising one."
    )


def readme_ablation(truth: dict) -> str:
    """README's one-paragraph summary of the ablation, stated from the deltas."""
    lead, reverse, _ = ablation_narrative(truth)
    deltas = {
        model: (truth[(EXP1, model)]["accuracy"] - truth[(EXP2, model)]["accuracy"]) * 100
        for model in {m for e, m in truth if e == EXP1} & {m for e, m in truth if e == EXP2}
    }
    hurt = [m for m, d in deltas.items() if d > 0]
    helped = sorted(((d, m) for m, d in deltas.items() if d <= 0))
    names = ", ".join(m.replace("_FineTuned", "") for _, m in helped)
    span = (
        f"by {abs(helped[-1][0]):.1f}-{abs(helped[0][0]):.1f} points"
        if len(helped) > 1
        else (f"by {abs(helped[0][0]):.1f} points" if helped else "")
    )
    tail = (
        f" The {len(helped)} weakest fine-tuned transformers ({names}) move the other way {span}, "
        f"but all sit well below the champion: trained for a single CPU-budgeted epoch, they never "
        f"learned to use the function-word signal in the first place."
        if helped
        else ""
    )
    return (
        f"Keeping Somali stopwords beats removing them for {len(hurt)} of the {len(deltas)} "
        f"benchmarked models — including every traditional-ML model and every BiLSTM variant — "
        f"under the expanded {STOPWORD_COUNT}-word list, since it strips common content words in "
        f"addition to grammatical function words.{tail}"
    )


def paper_md_margin(truth: dict) -> str:
    """research_paper.md's champion-margin sentence, recomputed."""
    a = lambda e, m: truth[(e, m)]["accuracy"] * 100  # noqa: E731
    m1 = a(EXP1, "LinearSVC_TFIDF") - a(EXP1, "LogisticRegression_TFIDF")
    m2 = a(EXP2, "LinearSVC_TFIDF") - a(EXP2, "LogisticRegression_TFIDF")
    verb = "widens" if m2 > m1 else "narrows"
    return (
        f"`LinearSVC_TFIDF` leads both experiments, and its margin over "
        f"`LogisticRegression_TFIDF` {verb} when\nthe stopword list is applied ({m1:.2f} points in "
        f"Experiment 1, {m2:.2f} in Experiment 2): the more aggressive\n{STOPWORD_COUNT}-word list "
        f"strips real content words alongside function words, which hurts logistic regression's\n"
        f"probabilistic objective more than the margin-maximising one."
    )


def replace_paragraph(text: str, start_anchor: str, new: str) -> str:
    """Swap the paragraph that begins with `start_anchor`, however it is line-wrapped.

    A bullet ends the paragraph as surely as a blank line does: the lead sentence runs
    straight into the ablation list with no blank line between them, and swallowing the
    bullets would delete the very block the next step needs to find.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith(start_anchor):
            continue
        end = i
        while end < len(lines) and lines[end].strip() and not lines[end].startswith("- "):
            end += 1
        return "\n".join(lines[:i] + [new] + lines[end:]) + ("\n" if text.endswith("\n") else "")
    raise LookupError(start_anchor)


def apply_chapter(truth, best_key, dry_run: bool) -> None:
    text = CHAPTER.read_text(encoding="utf-8")
    text = replace_markdown_table(text, r"^\| Experiment \| Model Family \|", block_chapter(truth, best_key))
    lead, reverse, robust = ablation_narrative(truth)
    text = replace_paragraph(text, "**Keeping Somali function words", lead)
    text = replace_bullets(text, block_ablation(truth))
    text = replace_paragraph(text, "The effect is not universal", reverse)
    text = replace_paragraph(text, "`LinearSVC_TFIDF` is also", robust)
    text = replace_paragraph(text, "Note: within Experiment 2 specifically", margin_note(truth))
    text = refresh_stopword_prose(text)
    write(CHAPTER, text, dry_run)


def apply_readme(truth, best_key, dry_run: bool) -> None:
    text = README.read_text(encoding="utf-8")
    text = replace_markdown_table(text, r"^\| Experiment \| Family \| Model \|", block_readme(truth, best_key))
    text = replace_paragraph(text, "Keeping Somali stopwords beats", readme_ablation(truth))
    write(README, refresh_stopword_prose(text), dry_run)


def paper_md_ablation(truth: dict) -> tuple[str, str, str]:
    """research_paper.md states the ablation three times over; all three are derived."""
    deltas = {
        model: (truth[(EXP1, model)]["accuracy"] - truth[(EXP2, model)]["accuracy"]) * 100
        for model in {m for e, m in truth if e == EXP1} & {m for e, m in truth if e == EXP2}
    }
    hurt = [m for m, d in deltas.items() if d > 0]
    helped = sorted(((d, m) for m, d in deltas.items() if d <= 0))
    a = lambda e, m: truth[(e, m)]["accuracy"] * 100  # noqa: E731

    lead = (
        f"Keeping Somali function words performs better for {len(hurt)} of the {len(deltas)} "
        f"benchmarked models — including every traditional-ML model and every BiLSTM variant:"
    )
    bullets = "\n".join(
        f"- `{m}`: {a(EXP1, m):.2f}% to {a(EXP2, m):.2f}% ({-deltas[m]:+.2f} pp)"
        for m in ["LinearSVC_TFIDF", "LogisticRegression_TFIDF", "XGBoost_TFIDF", "BiLSTM_Keras"]
    )
    moved = ", ".join(f"{m.replace('_FineTuned', '')} {a(EXP1, m):.2f}% to {a(EXP2, m):.2f}%" for _, m in helped)
    reverse = (
        f"The effect is not universal. {len(helped)} of the {len(deltas)} models improve slightly\n"
        f"without stopwords ({moved}). These are also among the weakest models in the study, well below the\n"
        f"champion: under a one-epoch CPU budget they never learn to exploit function-word distribution, so\n"
        f"removing those tokens costs them nothing. The result is therefore that function words carry\n"
        f"discriminative signal well-fitted models exploit and under-fitted ones cannot — not that stopword"
    )
    return lead, bullets, reverse


def apply_paper_md(truth, best_key, dry_run: bool) -> None:
    text = PAPER_MD.read_text(encoding="utf-8")
    text = replace_markdown_table(text, r"^\| Model \| Family \| Exp 1 Acc", block_paper(truth, best_key))
    text = replace_paragraph(text, "`LinearSVC_TFIDF` leads both experiments", paper_md_margin(truth))
    lead, bullets, reverse = paper_md_ablation(truth)
    text = replace_paragraph(text, "Keeping Somali function words performs better", lead)
    text = replace_bullets(text, bullets)
    text = replace_paragraph(text, "The effect is not universal.", reverse)
    write(PAPER_MD, refresh_stopword_prose(text), dry_run)


def apply_landing(truth, _best_key, dry_run: bool) -> None:
    text = LANDING.read_text(encoding="utf-8")
    match = re.search(r"const DEFAULT_MODELS(?::\s*ModelRow\[\])?\s*=\s*\[.*?\n\]", text, re.S)
    if not match:
        raise LookupError("DEFAULT_MODELS")
    # Keep the file's own declaration -- it may or may not carry the type annotation.
    declaration = match.group(0).split("[", 1)[0]
    body = block_landing(truth).split("[", 1)[1]
    text = text[: match.start()] + declaration + "[" + body + text[match.end() :]

    # The per-experiment stat tiles carry literal fallbacks for when the API is slow or
    # down, so a visitor who catches the page mid-load sees whatever was typed here.
    for exp in (EXP1, EXP2):
        acc = max(m["accuracy"] for (e, _), m in truth.items() if e == exp) * 100
        f1 = max(m["f1"] for (e, _), m in truth.items() if e == exp)
        text = re.sub(
            rf"(build\('{exp}',\s*')[\d.]+%(',\s*')[\d.]+(')",
            rf"\g<1>{acc:.2f}%\g<2>{f1:.4f}\g<3>",
            text,
        )
    write(LANDING, refresh_stopword_prose(text), dry_run)


def refresh_stopword_prose(text: str) -> str:
    """Retarget any prose that quotes an older stop-word list size.

    The count appears in a dozen phrasings and sometimes wraps mid-phrase, so this
    matches the number plus "-word" wherever it is followed, within the next few
    words, by something that identifies it as the stop-word list.
    """
    # "an earlier 60-word list" is a statement about history, not about the current
    # list -- rewriting it turns a true sentence into a contradiction of itself.  The
    # qualifier can sit on the previous line, so the check looks back through newlines
    # rather than using a fixed-width lookbehind.
    historical = re.compile(r"\b(earlier|previous|original|former|pre-)\s*$")
    pattern = re.compile(
        r"\b(?!" + str(STOPWORD_COUNT) + r"\b)\d{2,4}(?=-word\b(?:\W+\w+){0,4}?\W+"
        r"(?:list|stopword|stop-word|Somali function word)\b)",
        re.S,
    )

    def swap(match: re.Match) -> str:
        before = " ".join(text[max(0, match.start() - 40) : match.start()].split())
        return match.group(0) if historical.search(before + " ") else str(STOPWORD_COUNT)

    text = pattern.sub(swap, text)
    text = re.sub(r"(list of )\d{2,4}( Somali function words)", rf"\g<1>{STOPWORD_COUNT}\g<2>", text)
    text = re.sub(r"(list of )\d{2,4}( high-frequency Somali function words)",
                  rf"\g<1>{STOPWORD_COUNT}\g<2>", text)
    return text


TARGETS = {
    "chapter": apply_chapter,
    "readme": apply_readme,
    "paper": apply_paper_md,
    "landing": apply_landing,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", help="comma-separated subset of " + ", ".join(TARGETS))
    args = parser.parse_args()

    truth, errors = load_truth()
    if errors:
        print("Refusing to publish -- the reports do not agree with the splits:")
        for err in errors:
            print(f"  {err}")
        return 1
    best_key, best = champion(truth)
    print(f"{len(truth)} model results | champion {best_key[1]} {best['accuracy'] * 100:.2f}% "
          f"| stop-word list {STOPWORD_COUNT}\n")

    names = args.only.split(",") if args.only else list(TARGETS)
    for name in names:
        if name not in TARGETS:
            print(f"unknown target: {name}")
            return 1
        try:
            TARGETS[name](truth, best_key, args.dry_run)
        except LookupError as exc:
            print(f"  FAIL  {name}: anchor not found ({exc})")
            return 1

    print(f"\n{len(changed)} file(s) {'would change' if args.dry_run else 'changed'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
