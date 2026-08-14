from __future__ import annotations

from pathlib import Path

from experiments.run_completion_pass import train_hf_transformer
from experiments.run_full_12_steps import train_xlmr

EXP_DIR = Path("experiments") / "experiment_1_stopwords_included"
LABEL_NAMES = ["AI", "HUMAN"]
SEED = 42


def main() -> int:
    print("== experiment_1_stopwords_included: XLMRoberta_FineTuned (batch_size=32) ==", flush=True)
    print(train_xlmr(EXP_DIR, LABEL_NAMES, SEED, batch_size=32), flush=True)

    print("== experiment_1_stopwords_included: mBERT_FineTuned (batch_size=32) ==", flush=True)
    print(train_hf_transformer(
        EXP_DIR, LABEL_NAMES, SEED,
        "bert-base-multilingual-cased", "mBERT_FineTuned",
        batch_size=32,
    ), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
