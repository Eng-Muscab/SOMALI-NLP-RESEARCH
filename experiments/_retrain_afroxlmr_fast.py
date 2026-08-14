from __future__ import annotations

from pathlib import Path

from experiments.run_completion_pass import train_hf_transformer

EXP_DIR = Path("experiments") / "experiment_2_stopwords_removed"
LABEL_NAMES = ["AI", "HUMAN"]
SEED = 42


def main() -> int:
    print("== experiment_2_stopwords_removed: AfroXLMR_FineTuned (retry, batch_size=32) ==", flush=True)
    print(train_hf_transformer(
        EXP_DIR, LABEL_NAMES, SEED,
        "Davlan/afro-xlmr-base", "AfroXLMR_FineTuned",
        batch_size=32,
    ), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
