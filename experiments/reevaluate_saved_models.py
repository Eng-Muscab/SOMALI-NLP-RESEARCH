"""Re-evaluate saved models and regenerate classification reports."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())

import argparse
import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from experiments.run_completion_pass import rebuild_comparison_from_reports, write_step_report
from experiments.run_full_12_steps import TextDataset, TransformerBlock, metric_payload, save_dl_outputs


def evaluate_keras_model(
    exp_dir: Path,
    model_path: Path,
    model_name: str,
    family: str,
    label_names: list[str],
) -> dict[str, object]:
    data_dir = exp_dir / "data"
    test = joblib.load(data_dir / "test_tok.pkl")
    y_test_labels = np.array(test["labels"])
    custom_objects = {"TransformerBlock": TransformerBlock}
    model = tf.keras.models.load_model(model_path, compile=False, custom_objects=custom_objects)
    probabilities = model.predict(test["input_ids"], batch_size=128, verbose=0)
    pred_ids = np.argmax(probabilities, axis=1)
    y_pred = np.array([label_names[idx] for idx in pred_ids])
    positive_scores = probabilities[:, 1] if probabilities.shape[1] == 2 else None
    history = type("History", (), {"history": {}})()
    return save_dl_outputs(exp_dir, family, model_name, y_test_labels, y_pred, label_names, history, model, positive_scores)


def evaluate_xlmr(exp_dir: Path, label_names: list[str]) -> dict[str, object]:
    from sklearn.metrics import classification_report, confusion_matrix
    import matplotlib.pyplot as plt
    import seaborn as sns

    model_name = "XLMRoberta_FineTuned"
    data_dir = exp_dir / "data"
    reports_dir = exp_dir / "evaluation" / "reports"
    figures_dir = exp_dir / "evaluation" / "figures"
    model_dir = exp_dir / "models" / "transformers" / "xlm-roberta-base"
    test_df = pd.read_csv(data_dir / "clean_test.csv", keep_default_na=False)
    label2id = {label: idx for idx, label in enumerate(label_names)}
    id2label = {idx: label for label, idx in label2id.items()}
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    test_dataset = TextDataset(
        test_df["Text"].astype(str).tolist(),
        [label2id[label] for label in test_df["Label"].astype(str).tolist()],
        tokenizer,
        max_length=128,
    )
    loader = DataLoader(test_dataset, batch_size=16)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    pred_ids: list[int] = []
    with torch.no_grad():
        for batch in loader:
            batch.pop("labels")
            batch = {key: value.to(device) for key, value in batch.items()}
            pred_ids.extend(torch.argmax(model(**batch).logits, dim=-1).cpu().tolist())
    y_pred = np.array([id2label[idx] for idx in pred_ids])
    y_true = test_df["Label"].astype(str).to_numpy()
    train_rows = len(pd.read_csv(data_dir / "clean_train.csv", keep_default_na=False))
    val_rows = len(pd.read_csv(data_dir / "clean_val.csv", keep_default_na=False))
    evaluation_rows = train_rows + val_rows
    pd.DataFrame(
        classification_report(y_true, y_pred, labels=label_names, output_dict=True, zero_division=0)
    ).transpose().to_csv(reports_dir / f"classification_report_{model_name}.csv", index_label="label")
    (reports_dir / f"classification_report_{model_name}.txt").write_text(
        classification_report(y_true, y_pred, labels=label_names, zero_division=0),
        encoding="utf-8",
    )
    cm = confusion_matrix(y_true, y_pred, labels=label_names)
    plt.figure(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=label_names, yticklabels=label_names)
    plt.title(model_name)
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.tight_layout()
    plt.savefig(figures_dir / f"confusion_matrix_{model_name}.svg", dpi=180)
    plt.close()
    return {
        "experiment": exp_dir.name,
        "family": "transformers",
        "model": model_name,
        "evaluation_train_rows": evaluation_rows,
        "test_rows": int(len(test_df)),
        "final_train_rows": evaluation_rows,
        "saved_model_train_scope": "train_validation",
        **metric_payload(y_true, y_pred, label_names),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True)
    args = parser.parse_args()

    exp_dir = ROOT / "experiments" / args.experiment
    label_names = sorted(
        pd.read_csv(exp_dir / "data" / "clean_train.csv", keep_default_na=False)["Label"].astype(str).unique().tolist()
    )
    reports_dir = exp_dir / "evaluation" / "reports"
    if not (reports_dir / "classification_report_BiLSTM_Keras.csv").exists():
        evaluate_keras_model(
            exp_dir,
            exp_dir / "models" / "deep_learning" / "BiLSTM_Keras.keras",
            "BiLSTM_Keras",
            "deep_learning",
            label_names,
        )
    if not (reports_dir / "classification_report_MiniTransformer_Keras.csv").exists():
        evaluate_keras_model(
            exp_dir,
            exp_dir / "models" / "transformers" / "MiniTransformer_Keras.keras",
            "MiniTransformer_Keras",
            "transformers",
            label_names,
        )
    if not (reports_dir / "classification_report_XLMRoberta_FineTuned.csv").exists():
        evaluate_xlmr(exp_dir, label_names)
    rows = rebuild_comparison_from_reports(exp_dir)
    write_step_report(exp_dir, rows)
    print(f"Rebuilt comparison with {len(rows)} models for {args.experiment}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
