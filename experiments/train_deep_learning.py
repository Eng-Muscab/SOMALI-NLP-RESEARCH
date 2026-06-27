"""Train BiLSTM_Keras and MiniTransformer_Keras for both experiments."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = next(
    (p for p in [Path(__file__).resolve(), *Path(__file__).resolve().parents]
     if (p / "config.yaml").exists()),
    Path(__file__).resolve().parent.parent,
)
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import joblib
import pandas as pd

from experiments.run_full_12_steps import (
    tokenize_with_keras,
    train_bilstm,
    train_mini_transformer,
    TransformerBlock,
)

EXPERIMENTS = [
    "experiment_1_stopwords_included",
    "experiment_2_stopwords_removed",
]
LABEL_NAMES = ["AI", "HUMAN"]
SEED = 42


def main() -> None:
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    for exp_name in EXPERIMENTS:
        exp_dir = PROJECT_ROOT / "experiments" / exp_name
        data_dir = exp_dir / "data"
        print(f"\n{'='*60}")
        print(f"  Experiment: {exp_name}")
        print(f"{'='*60}")

        # Step 1 — build Keras tokenizer + tokenized splits
        tok_file = exp_dir / "data" / "tokenizer.joblib"
        if tok_file.exists():
            print("[1/3] tokenizer.joblib already exists — skipping tokenization.")
        else:
            print("[1/3] Tokenizing with Keras tokenizer …")
            tokenize_with_keras(exp_dir, max_tokens=30_000, max_length=256)
            print("      tokenizer.joblib + *_tok.pkl saved.")

        # Step 2 — train BiLSTM_Keras
        keras_path = exp_dir / "models" / "deep_learning" / "BiLSTM_Keras.keras"
        if keras_path.exists():
            print(f"[2/3] BiLSTM_Keras.keras already exists — skipping.")
        else:
            print("[2/3] Training BiLSTM_Keras …")
            metrics = train_bilstm(exp_dir, LABEL_NAMES, SEED)
            print(f"      acc={metrics.get('accuracy', 0):.4f}  f1={metrics.get('f1', 0):.4f}")

        # Step 3 — train MiniTransformer_Keras
        mini_path = exp_dir / "models" / "transformers" / "MiniTransformer_Keras.keras"
        if mini_path.exists():
            print(f"[3/3] MiniTransformer_Keras.keras already exists — skipping.")
        else:
            print("[3/3] Training MiniTransformer_Keras …")
            metrics = train_mini_transformer(exp_dir, LABEL_NAMES, SEED)
            print(f"      acc={metrics.get('accuracy', 0):.4f}  f1={metrics.get('f1', 0):.4f}")

    print("\nAll done!  Keras model files saved.")
    print("Reload the backend to pick up new models: POST /api/models/reload")


if __name__ == "__main__":
    main()
