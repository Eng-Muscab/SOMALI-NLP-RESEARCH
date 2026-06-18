from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


EXPERIMENTS = ["experiment_1_stopwords_included", "experiment_2_stopwords_removed"]
SAMPLE_TEXTS = [
    "waxbarashada casriga ah waxay ardayda siin kartaa fursado cusub oo ay ku hormariyaan aqoontooda",
    "maanta waxaan suuqa ka soo iibiyay khudaar kadibna guriga ayaan ku laabtay",
]

REQUIRED_KERAS = [
    ("BiLSTM_FastText", "deep_learning"),
    ("BiLSTM_Word2Vec", "deep_learning"),
    ("BiLSTM_MultilingualEmbeddings", "deep_learning"),
]

REQUIRED_TRANSFORMERS = [
    "mBERT_FineTuned",
    "SomBERTa_FineTuned",
    "AfroXLMR_FineTuned",
    "AfriBERTa_FineTuned",
]


def labels_for(exp_dir: Path) -> list[str]:
    train_df = pd.read_csv(exp_dir / "data" / "clean_train.csv", keep_default_na=False)
    return sorted(train_df["Label"].astype(str).unique().tolist())


def metric_payload(y_true, y_pred, labels):
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(report["weighted avg"]["precision"]),
        "recall": float(report["weighted avg"]["recall"]),
        "f1": float(report["weighted avg"]["f1-score"]),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def report_metrics(exp_dir: Path, model_name: str) -> dict[str, float] | None:
    path = exp_dir / "evaluation" / "reports" / f"classification_report_{model_name}.csv"
    if not path.exists():
        return None
    report = pd.read_csv(path, index_col=0)
    return {
        "accuracy": float(report.loc["accuracy", "precision"]),
        "precision": float(report.loc["weighted avg", "precision"]),
        "recall": float(report.loc["weighted avg", "recall"]),
        "f1": float(report.loc["weighted avg", "f1-score"]),
        "macro_f1": float(report.loc["macro avg", "f1-score"]),
    }


def compare(actual: dict[str, float], reported: dict[str, float] | None) -> dict[str, dict[str, float | None]]:
    if reported is None:
        return {}
    return {
        key: {
            "actual": float(actual[key]),
            "reported": float(reported[key]),
            "delta": float(actual[key] - reported[key]),
        }
        for key in ["accuracy", "precision", "recall", "f1", "macro_f1"]
    }


def verify_keras(exp_dir: Path, model_name: str, labels: list[str]) -> dict:
    import tensorflow as tf
    from tensorflow.keras.preprocessing.sequence import pad_sequences

    model_path = exp_dir / "models" / "deep_learning" / f"{model_name}.keras"
    row = {
        "experiment": exp_dir.name,
        "model": model_name,
        "family": "deep_learning",
        "artifact": str(model_path.relative_to(ROOT)),
        "artifact_exists": model_path.exists(),
        "loaded": False,
        "inference_ok": False,
    }
    try:
        model = tf.keras.models.load_model(model_path, compile=False)
        row["loaded"] = True
        test = joblib.load(exp_dir / "data" / "test_tok.pkl")
        y_true = np.asarray(test["labels"])
        probs = model.predict(test["input_ids"], batch_size=128, verbose=0)
        pred_ids = np.argmax(probs, axis=1)
        y_pred = np.asarray([labels[int(idx)] for idx in pred_ids])
        actual = metric_payload(y_true, y_pred, labels)
        row["metrics"] = actual
        row["reported_comparison"] = compare(actual, report_metrics(exp_dir, model_name))

        tok_meta = joblib.load(exp_dir / "data" / "tokenizer.joblib")
        tokenizer = tok_meta["tokenizer"]
        max_length = int(tok_meta["max_length"])
        sample_ids = pad_sequences(
            tokenizer.texts_to_sequences(SAMPLE_TEXTS),
            maxlen=max_length,
            padding="post",
            truncating="post",
        )
        sample_probs = model.predict(sample_ids, verbose=0)
        samples = []
        for text, values in zip(SAMPLE_TEXTS, sample_probs):
            pred_idx = int(np.argmax(values))
            samples.append(
                {
                    "text": text,
                    "prediction": labels[pred_idx],
                    "probabilities": {labels[i]: float(v) for i, v in enumerate(values)},
                }
            )
        row["sample_predictions"] = samples
        row["inference_ok"] = True
    except Exception as exc:
        row["error"] = repr(exc)
    return row


def verify_transformer(exp_dir: Path, model_name: str, labels: list[str]) -> dict:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from experiments.run_full_12_steps import TextDataset

    model_dir = exp_dir / "models" / "transformers" / model_name
    weight_path = model_dir / "model.safetensors"
    if not weight_path.exists():
        weight_path = model_dir / "pytorch_model.bin"
    row = {
        "experiment": exp_dir.name,
        "model": model_name,
        "family": "transformers",
        "artifact": str(weight_path.relative_to(ROOT)) if weight_path.exists() else str(model_dir.relative_to(ROOT)),
        "artifact_exists": weight_path.exists(),
        "loaded": False,
        "inference_ok": False,
    }
    try:
        label2id = {label: idx for idx, label in enumerate(labels)}
        id2label = {idx: label for label, idx in label2id.items()}
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        row["loaded"] = True
        test_df = pd.read_csv(exp_dir / "data" / "clean_test.csv", keep_default_na=False)
        ds = TextDataset(
            test_df["Text"].astype(str).tolist(),
            [label2id[label] for label in test_df["Label"].astype(str).tolist()],
            tokenizer,
            max_length=128,
        )
        loader = DataLoader(ds, batch_size=16)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()
        pred_ids = []
        with torch.no_grad():
            for batch in loader:
                batch.pop("labels")
                batch = {key: value.to(device) for key, value in batch.items()}
                logits = model(**batch).logits
                pred_ids.extend(torch.argmax(logits, dim=-1).cpu().tolist())
        y_pred = np.asarray([id2label[int(idx)] for idx in pred_ids])
        y_true = test_df["Label"].astype(str).to_numpy()
        actual = metric_payload(y_true, y_pred, labels)
        row["metrics"] = actual
        row["reported_comparison"] = compare(actual, report_metrics(exp_dir, model_name))

        enc = tokenizer(SAMPLE_TEXTS, truncation=True, padding=True, max_length=128, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**enc).logits.detach().cpu().numpy()
        exp_values = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp_values / exp_values.sum(axis=1, keepdims=True)
        samples = []
        for text, values in zip(SAMPLE_TEXTS, probs):
            pred_idx = int(np.argmax(values))
            samples.append(
                {
                    "text": text,
                    "prediction": id2label[pred_idx],
                    "probabilities": {id2label[i]: float(v) for i, v in enumerate(values)},
                }
            )
        row["sample_predictions"] = samples
        row["inference_ok"] = True
    except Exception as exc:
        row["error"] = repr(exc)
    return row


def main() -> int:
    rows = []
    for exp_name in EXPERIMENTS:
        exp_dir = ROOT / "experiments" / exp_name
        labels = labels_for(exp_dir)
        for model_name, _family in REQUIRED_KERAS:
            rows.append(verify_keras(exp_dir, model_name, labels))
        for model_name in REQUIRED_TRANSFORMERS:
            rows.append(verify_transformer(exp_dir, model_name, labels))

    payload = {
        "summary": {
            "total_required_artifacts": len(rows),
            "verified": sum(1 for row in rows if row["artifact_exists"] and row["loaded"] and row["inference_ok"]),
            "failed": sum(1 for row in rows if not (row["artifact_exists"] and row["loaded"] and row["inference_ok"])),
        },
        "results": rows,
    }
    out_path = ROOT / "required_models_verification.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
