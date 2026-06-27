"""Train BiLSTM_Word2Vec and BiLSTM_FastText for both experiments."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next(
    (p for p in [Path(__file__).resolve(), *Path(__file__).resolve().parents]
     if (p / "config.yaml").exists()),
    Path(__file__).resolve().parent.parent,
)
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

import numpy as np
import joblib
from experiments.run_completion_pass import train_bilstm_with_embeddings, keras_artifact_exists

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
        print(f"\n{'='*60}")
        print(f"  Experiment: {exp_name}")
        print(f"{'='*60}")

        for emb_type, model_name in [("word2vec", "BiLSTM_Word2Vec"), ("fasttext", "BiLSTM_FastText")]:
            if keras_artifact_exists(exp_dir, model_name):
                print(f"[SKIP] {model_name}.keras already exists.")
            else:
                print(f"[TRAIN] {model_name} ...")
                metrics = train_bilstm_with_embeddings(exp_dir, LABEL_NAMES, SEED, emb_type, model_name)
                print(f"       acc={metrics.get('accuracy', 0):.4f}  f1={metrics.get('f1', 0):.4f}")

    print("\nAll done! Reload backend: POST /api/models/reload")


if __name__ == "__main__":
    main()
