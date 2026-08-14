from __future__ import annotations

from pathlib import Path

from experiments.run_completion_pass import TRANSFORMER_SPECS, train_hf_transformer

EXP_DIR = Path("experiments") / "experiment_2_stopwords_removed"
LABEL_NAMES = ["AI", "HUMAN"]
SEED = 42


def main() -> int:
    for model_id, model_name in TRANSFORMER_SPECS:
        print(f"== experiment_2_stopwords_removed: {model_name} ==", flush=True)
        print(train_hf_transformer(EXP_DIR, LABEL_NAMES, SEED, model_id, model_name), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
