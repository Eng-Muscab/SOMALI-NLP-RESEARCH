from __future__ import annotations

from pathlib import Path

from experiments.run_completion_pass import train_hf_transformer

EXP_DIR = Path("experiments") / "experiment_1_stopwords_included"
LABEL_NAMES = ["AI", "HUMAN"]
SEED = 42

SPECS = [
    ("shuabdaud/SomBERTa", "SomBERTa_FineTuned"),
    ("castorini/afriberta_base", "AfriBERTa_FineTuned"),
    ("Davlan/afro-xlmr-base", "AfroXLMR_FineTuned"),
]


def main() -> int:
    for model_id, model_name in SPECS:
        print(f"== experiment_1_stopwords_included: {model_name} (batch_size=32) ==", flush=True)
        print(train_hf_transformer(
            EXP_DIR, LABEL_NAMES, SEED,
            model_id, model_name,
            batch_size=32,
        ), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
