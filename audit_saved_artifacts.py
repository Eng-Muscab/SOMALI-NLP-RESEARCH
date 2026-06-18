from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from experiments.run_full_12_steps import TextDataset, TransformerBlock


EXPERIMENTS = ["experiment_1_stopwords_included", "experiment_2_stopwords_removed"]
SAMPLES = [
    "waxbarashada casriga ah waxay ardayda siin kartaa fursado cusub oo ay ku hormariyaan aqoontooda",
    "maanta waxaan suuqa ka soo iibiyay khudaar kadibna guriga ayaan ku laabtay",
]


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


def reported_rows():
    path = ROOT / "experiments" / "full_12_step_run_summary.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        (row["experiment"], row["model"]): row
        for row in data.get("model_rows", [])
    }


def compare(actual, reported):
    if not reported:
        return {"status": "missing_reported_row"}
    out = {}
    for key in ["accuracy", "precision", "recall", "f1", "macro_f1"]:
        out[key] = {
            "actual": actual.get(key),
            "reported": reported.get(key),
            "delta": None if actual.get(key) is None else float(actual[key] - reported.get(key, math.nan)),
        }
    return out


def probabilities_from_model(model, texts, pred):
    classes = [str(item) for item in getattr(model, "classes_", [])]
    if not classes and hasattr(model, "named_steps"):
        clf = model.named_steps.get("clf")
        classes = [str(item) for item in getattr(clf, "classes_", [])]
    if hasattr(model, "predict_proba"):
        vals = model.predict_proba(texts)[0]
        return {cls: float(prob) for cls, prob in zip(classes, vals)}
    if hasattr(model, "decision_function"):
        raw = np.asarray(model.decision_function(texts))
        scores = raw[0] if raw.ndim > 1 else raw
        if np.asarray(scores).size == 1:
            score = float(np.asarray(scores).reshape(-1)[0])
            pos = 1.0 / (1.0 + math.exp(-score))
            if len(classes) == 2:
                return {classes[0]: float(1.0 - pos), classes[1]: float(pos)}
        scores = np.asarray(scores, dtype=float)
        exp = np.exp(scores - np.max(scores))
        probs = exp / exp.sum()
        return {cls: float(prob) for cls, prob in zip(classes, probs)}
    return {str(pred): 1.0}


def audit_traditional(exp_dir, labels, reported):
    rows = []
    test_df = pd.read_csv(exp_dir / "data" / "clean_test.csv", keep_default_na=False)
    x_test = test_df["Text"].astype(str).tolist()
    y_true = test_df["Label"].map({label: idx for idx, label in enumerate(labels)}).to_numpy(dtype=int)
    for path in sorted((exp_dir / "models" / "traditional_ml").glob("*.joblib")):
        model_name = path.stem
        row = {
            "experiment": exp_dir.name,
            "family": "traditional_ml",
            "model": model_name,
            "artifact": str(path.relative_to(ROOT)),
            "artifact_exists": path.exists(),
            "loaded": False,
            "inference_ok": False,
            "notes": [],
        }
        try:
            model = joblib.load(path)
            row["loaded"] = hasattr(model, "predict")
            preds = model.predict(x_test)
            actual = metric_payload(y_true, preds, list(range(len(labels))))
            row["fresh_saved_artifact_metrics_on_test_split"] = actual
            row["comparison_to_reported"] = compare(actual, reported.get((exp_dir.name, model_name)))
            sample_pred = model.predict([SAMPLES[0]])[0]
            row["sample_predictions"] = [{
                "text": SAMPLES[0],
                "prediction_raw": int(sample_pred) if isinstance(sample_pred, (np.integer, int)) else str(sample_pred),
                "prediction_label": labels[int(sample_pred)] if str(sample_pred).isdigit() else str(sample_pred),
                "probabilities": probabilities_from_model(model, [SAMPLES[0]], sample_pred),
            }]
            row["inference_ok"] = True
            row["notes"].append("Saved traditional models were refit on train+val+test after evaluation, so fresh test metrics are leakage-affected.")
        except Exception as exc:
            row["error"] = repr(exc)
        rows.append(row)
    return rows


def audit_keras(exp_dir, labels, reported):
    import tensorflow as tf

    rows = []
    label2id = {label: idx for idx, label in enumerate(labels)}
    id2label = {idx: label for label, idx in label2id.items()}
    test = joblib.load(exp_dir / "data" / "test_tok.pkl")
    y_true_labels = np.asarray(test["labels"])
    tok_meta = joblib.load(exp_dir / "data" / "tokenizer.joblib")
    tokenizer = tok_meta["tokenizer"]
    max_length = int(tok_meta["max_length"])
    from tensorflow.keras.preprocessing.sequence import pad_sequences

    artifacts = [
        (exp_dir / "models" / "deep_learning" / "BiLSTM_Keras.keras", "deep_learning", "BiLSTM_Keras"),
        (exp_dir / "models" / "transformers" / "MiniTransformer_Keras.keras", "transformers", "MiniTransformer_Keras"),
    ]
    for path, family, model_name in artifacts:
        row = {
            "experiment": exp_dir.name,
            "family": family,
            "model": model_name,
            "artifact": str(path.relative_to(ROOT)),
            "artifact_exists": path.exists(),
            "loaded": False,
            "inference_ok": False,
            "training_log_exists": (path.parent / f"{model_name}_training_log.csv").exists(),
        }
        try:
            model = tf.keras.models.load_model(path, compile=False, custom_objects={"TransformerBlock": TransformerBlock})
            row["loaded"] = True
            probs = model.predict(test["input_ids"], batch_size=128, verbose=0)
            pred_ids = np.argmax(probs, axis=1)
            y_pred = np.array([id2label[int(idx)] for idx in pred_ids])
            actual = metric_payload(y_true_labels, y_pred, labels)
            row["fresh_saved_artifact_metrics_on_test_split"] = actual
            row["comparison_to_reported"] = compare(actual, reported.get((exp_dir.name, model_name)))
            sample_ids = pad_sequences(tokenizer.texts_to_sequences([SAMPLES[0]]), maxlen=max_length, padding="post", truncating="post")
            sample_probs = model.predict(sample_ids, verbose=0)[0]
            sample_idx = int(np.argmax(sample_probs))
            row["sample_predictions"] = [{
                "text": SAMPLES[0],
                "prediction_label": id2label[sample_idx],
                "probabilities": {id2label[i]: float(v) for i, v in enumerate(sample_probs)},
            }]
            row["inference_ok"] = True
        except Exception as exc:
            row["error"] = repr(exc)
        rows.append(row)
    return rows


def audit_xlmr(exp_dir, labels, reported):
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    model_dir = exp_dir / "models" / "transformers" / "xlm-roberta-base"
    row = {
        "experiment": exp_dir.name,
        "family": "transformers",
        "model": "XLMRoberta_FineTuned",
        "artifact": str((model_dir / "model.safetensors").relative_to(ROOT)),
        "artifact_exists": (model_dir / "model.safetensors").exists(),
        "loaded": False,
        "inference_ok": False,
        "training_log_exists": (model_dir / "xlm_roberta_training_log.csv").exists(),
    }
    try:
        label2id = {label: idx for idx, label in enumerate(labels)}
        id2label = {idx: label for label, idx in label2id.items()}
        test_df = pd.read_csv(exp_dir / "data" / "clean_test.csv", keep_default_na=False)
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        row["loaded"] = True
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
                pred_ids.extend(torch.argmax(model(**batch).logits, dim=-1).cpu().tolist())
        y_pred = np.array([id2label[int(idx)] for idx in pred_ids])
        y_true = test_df["Label"].astype(str).to_numpy()
        actual = metric_payload(y_true, y_pred, labels)
        row["fresh_saved_artifact_metrics_on_test_split"] = actual
        row["comparison_to_reported"] = compare(actual, reported.get((exp_dir.name, "XLMRoberta_FineTuned")))
        enc = tokenizer([SAMPLES[0]], truncation=True, padding=True, max_length=128, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**enc).logits[0].cpu().numpy()
        exp = np.exp(logits - np.max(logits))
        probs = exp / exp.sum()
        sample_idx = int(np.argmax(probs))
        row["sample_predictions"] = [{
            "text": SAMPLES[0],
            "prediction_label": id2label[sample_idx],
            "probabilities": {id2label[i]: float(v) for i, v in enumerate(probs)},
        }]
        row["inference_ok"] = True
    except Exception as exc:
        row["error"] = repr(exc)
    return row


def missing_expected(exp_dir):
    expected = [
        ("Naive Bayes", exp_dir / "models" / "traditional_ml" / "NaiveBayes_TFIDF.joblib"),
        ("LSTM", exp_dir / "models" / "deep_learning" / "LSTM_Keras.keras"),
        ("CNN", exp_dir / "models" / "deep_learning" / "CNN_Keras.keras"),
        ("GRU", exp_dir / "models" / "deep_learning" / "GRU_Keras.keras"),
        ("BERT", exp_dir / "models" / "transformers" / "bert-base-multilingual-cased" / "model.safetensors"),
        ("RoBERTa", exp_dir / "models" / "transformers" / "roberta-base" / "model.safetensors"),
        ("DistilBERT", exp_dir / "models" / "transformers" / "distilbert-base-multilingual-cased" / "model.safetensors"),
    ]
    return [
        {
            "experiment": exp_dir.name,
            "model": name,
            "status": "Missing",
            "expected_artifact": str(path.relative_to(ROOT)),
            "artifact_exists": path.exists(),
        }
        for name, path in expected
        if not path.exists()
    ]


def main():
    reported = reported_rows()
    output = {"artifacts": [], "missing_expected_models": [], "log_audit": [], "report_files": []}
    for exp_name in EXPERIMENTS:
        exp_dir = ROOT / "experiments" / exp_name
        labels = sorted(pd.read_csv(exp_dir / "data" / "clean_train.csv", keep_default_na=False)["Label"].astype(str).unique().tolist())
        output["artifacts"].extend(audit_traditional(exp_dir, labels, reported))
        output["artifacts"].extend(audit_keras(exp_dir, labels, reported))
        output["artifacts"].append(audit_xlmr(exp_dir, labels, reported))
        output["missing_expected_models"].extend(missing_expected(exp_dir))
        for log in sorted((exp_dir / "models").rglob("*training_log.csv")):
            try:
                rows = len(pd.read_csv(log))
            except Exception:
                rows = None
            output["log_audit"].append({"file": str(log.relative_to(ROOT)), "exists": log.exists(), "rows": rows})
        for report in sorted((exp_dir / "evaluation" / "reports").glob("classification_report_*.csv")):
            output["report_files"].append({"file": str(report.relative_to(ROOT)), "exists": report.exists()})
    out_path = ROOT / "audit_verification_results.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(json.dumps({
        "verified_artifacts": sum(1 for row in output["artifacts"] if row.get("loaded") and row.get("inference_ok")),
        "failed_artifacts": sum(1 for row in output["artifacts"] if not (row.get("loaded") and row.get("inference_ok"))),
        "missing_expected_models": len(output["missing_expected_models"]),
    }, indent=2))


if __name__ == "__main__":
    main()
