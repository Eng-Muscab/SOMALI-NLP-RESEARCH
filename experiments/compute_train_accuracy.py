"""Score every saved model on its own training split, for the train/test columns.

The paper reports test accuracy only, so a reader cannot see how much of the gap
between models is over-fitting.  This re-scores each saved model on the data it was
fitted on and writes `evaluation/reports/train_accuracy.csv` per experiment.

Nothing is retrained: every model is loaded from disk and run forward once.  The
traditional and Keras models take seconds; the five fine-tuned transformers dominate
the runtime at roughly ten minutes each on CPU.

Note on what "train" means here, because the two families were fitted differently:
traditional-ML models are refitted on train+val+test for deployment, so their training
score is reported on train+val (the data used for the reported evaluation fit); every
other model is fitted on train only and is scored on train.

    python experiments/compute_train_accuracy.py [--experiment NAME] [--skip-transformers]
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPERIMENTS = ["experiment_1_stopwords_included", "experiment_2_stopwords_removed"]
LABEL_NAMES = ["AI", "HUMAN"]
TRANSFORMER_DIRS = {
    "XLMRoberta_FineTuned": "xlm-roberta-base",
    "mBERT_FineTuned": "mBERT_FineTuned",
    "SomBERTa_FineTuned": "SomBERTa_FineTuned",
    "AfroXLMR_FineTuned": "AfroXLMR_FineTuned",
    "AfriBERTa_FineTuned": "AfriBERTa_FineTuned",
}


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def train_frame(exp_dir: Path, scope: str) -> pd.DataFrame:
    names = ["clean_train.csv", "clean_val.csv"] if scope == "train_validation" else ["clean_train.csv"]
    return pd.concat(
        [pd.read_csv(exp_dir / "data" / n, keep_default_na=False) for n in names],
        ignore_index=True,
    )


def score(y_true, y_pred) -> float:
    return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))


def traditional(exp_dir: Path) -> dict[str, float]:
    import joblib

    out = {}
    df = train_frame(exp_dir, "train_validation")
    x, y = df["Text"].astype(str).tolist(), df["Label"].astype(str).to_numpy()
    for path in sorted((exp_dir / "models" / "traditional_ml").glob("*.joblib")):
        model = joblib.load(path)
        pred = model.predict(x)
        if pred.dtype.kind in "iu":
            pred = np.array([LABEL_NAMES[i] for i in pred])
        out[path.stem] = score(y, pred)
        log(f"    {path.stem:28s} {out[path.stem]:.4f}")
    return out


def keras_models(exp_dir: Path) -> dict[str, float]:
    import joblib
    import tensorflow as tf

    from experiments.transformer_block import TransformerBlock

    tf.get_logger().setLevel("ERROR")
    tok = joblib.load(exp_dir / "data" / "train_tok.pkl")
    y = np.array(tok["labels"])
    out = {}
    paths = list((exp_dir / "models" / "deep_learning").glob("*.keras"))
    paths += list((exp_dir / "models" / "transformers").glob("MiniTransformer*.keras"))
    for path in sorted(paths):
        model = tf.keras.models.load_model(
            path, compile=False, custom_objects={"TransformerBlock": TransformerBlock}
        )
        probs = model.predict(tok["input_ids"], batch_size=128, verbose=0)
        pred = np.array([LABEL_NAMES[i] for i in np.argmax(probs, axis=1)])
        out[path.stem] = score(y, pred)
        log(f"    {path.stem:28s} {out[path.stem]:.4f}")
    return out


def transformers(exp_dir: Path) -> dict[str, float]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    from experiments.run_full_12_steps import TextDataset

    df = train_frame(exp_dir, "train")
    texts = df["Text"].astype(str).tolist()
    label2id = {label: i for i, label in enumerate(LABEL_NAMES)}
    labels = [label2id[v] for v in df["Label"].astype(str)]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    out = {}
    for name, folder in TRANSFORMER_DIRS.items():
        model_dir = exp_dir / "models" / "transformers" / folder
        if not model_dir.exists():
            log(f"    {name:28s} SKIP (no saved model)")
            continue
        started = time.time()
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(device).eval()
        loader = DataLoader(TextDataset(texts, labels, tokenizer, max_length=128), batch_size=32)
        preds: list[int] = []
        with torch.no_grad():
            for batch in loader:
                logits = model(
                    input_ids=batch["input_ids"].to(device),
                    attention_mask=batch["attention_mask"].to(device),
                ).logits
                preds.extend(torch.argmax(logits, dim=1).cpu().tolist())
        out[name] = score(labels, preds)
        log(f"    {name:28s} {out[name]:.4f}  ({(time.time() - started) / 60:.1f} min)")
        del model
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", action="append", dest="experiments")
    parser.add_argument("--skip-transformers", action="store_true")
    args = parser.parse_args()

    for exp in args.experiments or EXPERIMENTS:
        exp_dir = ROOT / "experiments" / exp
        out = exp_dir / "evaluation" / "reports" / "train_accuracy.csv"
        log(f"== {exp} ==")
        scores: dict[str, float] = {}

        def flush() -> None:
            # Written after each family: the transformer pass runs for the best part of
            # an hour, and losing the cheap scores to an interrupted run wastes a rerun.
            rows = [{"model": m, "train_accuracy": a} for m, a in sorted(scores.items())]
            pd.DataFrame(rows).to_csv(out, index=False)

        log("  traditional ML")
        scores.update(traditional(exp_dir))
        flush()
        log("  keras models")
        scores.update(keras_models(exp_dir))
        flush()
        if not args.skip_transformers:
            log("  fine-tuned transformers")
            scores.update(transformers(exp_dir))
            flush()
        log(f"  wrote {out.relative_to(ROOT)} ({len(scores)} models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
