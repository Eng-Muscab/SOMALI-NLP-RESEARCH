"""Rebuild the Experiment 2 splits from the Experiment 1 splits after a stop-word change.

Experiment 2 is an ablation: same rows, same split assignment, one variable changed.
So it is derived from the Experiment 1 splits on disk rather than rebuilt from the
raw workbook.  Rebuilding from raw would reintroduce a 4-row drift -- the raw file
has been edited since Experiment 1 was generated, and re-running the dataset builder
now yields 7,967/1,707/1,708 where Experiment 1 on disk (and the paper) has
7,970/1,708/1,708.  Deriving from Experiment 1 keeps the two experiments paired and
keeps the corpus size the paper quotes correct.

Rows whose text becomes empty once the function words are gone are dropped; with the
483-word list that is a handful of very short texts, reported at the end.

    python experiments/regenerate_exp2_splits.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.somali_stopwords import (  # noqa: E402
    SOMALI_FUNCTION_WORDS,
    STOPWORD_COUNT,
    remove_function_words,
)

EXP1_DATA = ROOT / "experiments" / "experiment_1_stopwords_included" / "data"
EXP2_DATA = ROOT / "experiments" / "experiment_2_stopwords_removed" / "data"
SPLITS = ("train", "val", "test")


def main() -> int:
    print(f"Stop-word list: {STOPWORD_COUNT} words")

    backup = EXP2_DATA / "_pre_483_backup"
    backup.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        for name in (f"{split}.csv", f"clean_{split}.csv"):
            src = EXP2_DATA / name
            if src.exists():
                shutil.copy2(src, backup / name)
    print(f"previous splits copied to {backup.relative_to(ROOT)}\n")

    # Mirror Experiment 1 file for file.  `clean_*.csv` is what every trainer reads and
    # carries 4 duplicate rows that `*.csv` does not; both are reproduced as they are so
    # the two experiments stay row-for-row paired and the corpus size the paper quotes
    # (11,386) keeps referring to the same rows.
    total_before = total_after = 0
    for name in [f"clean_{s}.csv" for s in SPLITS] + [f"{s}.csv" for s in SPLITS] + [
        "full_labeled_dataset.csv",
        "balanced_labeled_dataset.csv",
    ]:
        src = EXP1_DATA / name
        if not src.exists():
            print(f"  skip  {name} (not in Experiment 1)")
            continue
        source = pd.read_csv(src, keep_default_na=False)
        df = source.copy()
        df["Text"] = df["Text"].map(remove_function_words).fillna("").astype(str).str.strip()
        dropped = int((df["Text"].str.len() == 0).sum())
        df = df[df["Text"].str.len() > 0].copy()
        df.to_csv(EXP2_DATA / name, index=False)

        if name.startswith("clean_"):
            total_before += len(source)
            total_after += len(df)
        counts = df["Label"].value_counts().to_dict()
        print(
            f"  {name:28s} {len(source):>6,} -> {len(df):>6,} ({dropped} emptied)  "
            f"AI={counts.get('AI', 0):,} HUMAN={counts.get('HUMAN', 0):,}"
        )

    print(f"\nExperiment 2 training rows: {total_after:,} (Experiment 1 has {total_before:,})")

    leaked = set()
    for split in SPLITS:
        df = pd.read_csv(EXP2_DATA / f"clean_{split}.csv", keep_default_na=False)
        for text in df["Text"].astype(str):
            leaked |= set(text.split()) & SOMALI_FUNCTION_WORDS
    if leaked:
        print(f"FAIL: {len(leaked)} stop words survived: {sorted(leaked)[:12]}")
        return 1
    print(f"clean - none of the {STOPWORD_COUNT} function words remain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
