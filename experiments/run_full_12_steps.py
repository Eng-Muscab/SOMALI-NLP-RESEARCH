from __future__ import annotations

import json
import math
import re
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import tensorflow as tf
import yaml
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, roc_curve
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from experiments.run_balanced_experiments import (
    LabelSpec,
    build_experiment_dataset,
    compute_inter_annotator_agreement,
    generate_xai_outputs,
    generate_xai_outputs_strict,
    load_config,
    load_table,
    normalize_category,
    resolve_path,
    stratified_split_by_source,
    train_traditional_models,
    write_experiment_config,
    write_split_files,
)
from experiments.run_stopword_ablation import remove_function_words
EXPERIMENTS = [
    ("experiment_1_stopwords_included", False, "Clean text with Somali function words kept."),
    ("experiment_2_stopwords_removed", True, "Clean text with selected Somali function words removed."),
]


def safe_div(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_hf_model_with_fallback(model, tokenizer, model_dir: Path) -> Path:
    model_dir.mkdir(parents=True, exist_ok=True)
    try:
        model.save_pretrained(model_dir, safe_serialization=False)
        tokenizer.save_pretrained(model_dir)
        return model_dir
    except Exception as exc:
        fallback_dir = model_dir.parent / f"{model_dir.name}_balanced_refresh"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        print(f"== Save to {model_dir} failed ({exc}); saving to {fallback_dir} ==")
        model.save_pretrained(fallback_dir, safe_serialization=False)
        tokenizer.save_pretrained(fallback_dir)
        return fallback_dir


def generate_eda(exp_dir: Path) -> None:
    data_path = exp_dir / "data" / "train.csv"
    df = pd.read_csv(data_path, keep_default_na=False)
    figures_dir = exp_dir / "eda" / "figures"
    reports_dir = exp_dir / "eda" / "reports"
    figures_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    label_counts = df["Label"].value_counts().sort_index()
    plt.figure(figsize=(5, 4))
    sns.barplot(x=label_counts.index, y=label_counts.values, hue=label_counts.index, palette="Set2", legend=False)
    plt.title("Class distribution")
    plt.xlabel("Label")
    plt.ylabel("Rows")
    plt.tight_layout()
    plt.savefig(figures_dir / "class_distribution.svg", dpi=180)
    plt.close()

    lengths = df["Text"].astype(str).str.split().map(len)
    plt.figure(figsize=(7, 4))
    sns.histplot(lengths, bins=40, color="#2f6f9f")
    plt.title("Token length distribution")
    plt.xlabel("Word count")
    plt.ylabel("Rows")
    plt.tight_layout()
    plt.savefig(figures_dir / "sentence_length_hist.svg", dpi=180)
    plt.close()

    token_counts: dict[str, int] = {}
    for text in df["Text"].astype(str):
        for token in re.findall(r"\b\w+\b", text.lower()):
            if len(token) < 3:
                continue
            token_counts[token] = token_counts.get(token, 0) + 1
    top_words = pd.DataFrame(
        sorted(token_counts.items(), key=lambda item: item[1], reverse=True)[:30],
        columns=["word", "count"],
    )
    top_words.to_csv(reports_dir / "top_words.csv", index=False)
    plt.figure(figsize=(8, 7))
    sns.barplot(data=top_words.head(20), y="word", x="count", color="#4c956c")
    plt.title("Top words")
    plt.xlabel("Count")
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig(figures_dir / "top20_words.svg", dpi=180)
    plt.close()

    summary = {
        "rows": int(len(df)),
        "label_counts": {k: int(v) for k, v in label_counts.to_dict().items()},
        "word_count_mean": float(lengths.mean()),
        "word_count_median": float(lengths.median()),
        "word_count_max": int(lengths.max()),
    }

    cfg = load_config(ROOT / "config.yaml")
    supplemental_value = cfg.get("data", {}).get("supplemental_raw") or cfg.get("paths", {}).get("data_raw")
    supplemental_path = resolve_path(ROOT, supplemental_value) if supplemental_value else ROOT / "data" / "raw" / "full_dataset.xlsx"
    if not supplemental_path.exists():
        fallback = ROOT / "data" / "raw" / "full_dataset.csv"
        supplemental_path = fallback if fallback.exists() else supplemental_path
    if supplemental_path.exists():
        raw_df = load_table(supplemental_path).fillna("")

        if "Ai Type" in raw_df.columns:
            def normalize_tool(value: object) -> str | None:
                text = re.sub(r"[^a-z]", "", str(value).lower())
                if "chatgpt" in text or "gpt" in text:
                    return "ChatGPT"
                if "gemini" in text:
                    return "Gemini"
                if any(token in text for token in ("claude", "cloude", "cloud", "cluade")):
                    return "Claude"
                return None

            raw_df["ai_tool"] = raw_df["Ai Type"].map(normalize_tool)
            ai_counts = raw_df["ai_tool"].dropna().value_counts()
            if not ai_counts.empty:
                plt.figure(figsize=(6, 6))
                plt.pie(ai_counts.values, labels=ai_counts.index, autopct="%1.1f%%", startangle=90)
                plt.title("AI type distribution")
                plt.tight_layout()
                plt.savefig(figures_dir / "ai_type_distribution.svg", dpi=180)
                plt.close()
                summary["ai_type_counts"] = {k: int(v) for k, v in ai_counts.to_dict().items()}

            if "Category" in raw_df.columns:
                raw_df["Category"] = raw_df["Category"].map(normalize_category)
                category_counts = raw_df[raw_df["Category"].ne("Unknown")]["Category"].value_counts()
                if not category_counts.empty:
                    plt.figure(figsize=(10, 5))
                    ax = sns.barplot(x=category_counts.index, y=category_counts.values, color="#4c72b0")
                    for container in ax.containers:
                        ax.bar_label(container, fmt="%d", padding=3, fontsize=8)
                    plt.title("Category distribution")
                    plt.xlabel("Category")
                    plt.ylabel("Rows")
                    plt.xticks(rotation=45, ha="right")
                    plt.tight_layout()
                    plt.savefig(figures_dir / "category_distribution.svg", dpi=180)
                    plt.close()
                    summary["category_counts"] = {k: int(v) for k, v in category_counts.to_dict().items()}

                ai_df = raw_df[raw_df["ai_tool"].notna() & raw_df["Category"].ne("Unknown")]
                if not ai_df.empty:
                    pivot = ai_df.groupby(["Category", "ai_tool"]).size().unstack(fill_value=0)
                    if not category_counts.empty:
                        pivot = pivot.reindex(category_counts.index, fill_value=0)
                    ax = pivot.plot(kind="bar", stacked=True, figsize=(11, 5))
                    totals = pivot.sum(axis=1)
                    for idx, total in enumerate(totals):
                        ax.text(idx, total + totals.max() * 0.015, str(int(total)), ha="center", va="bottom", fontsize=8)
                    ax.set_ylim(0, totals.max() * 1.14)
                    plt.title("AI type by category")
                    plt.xlabel("Category")
                    plt.ylabel("Rows")
                    plt.xticks(rotation=45, ha="right")
                    plt.legend(title="AI Type")
                    plt.tight_layout()
                    plt.savefig(figures_dir / "ai_type_by_category.svg", dpi=180)
                    plt.close()

                    category_ai_counts = ai_df["Category"].value_counts()
                    if not category_counts.empty:
                        category_ai_counts = category_ai_counts.reindex(category_counts.index, fill_value=0)
                    plt.figure(figsize=(10, 5))
                    ax = sns.barplot(x=category_ai_counts.index, y=category_ai_counts.values, color="#55a868")
                    for container in ax.containers:
                        ax.bar_label(container, fmt="%d", padding=3, fontsize=8)
                    plt.title("AI-generated articles by category")
                    plt.xlabel("Category")
                    plt.ylabel("Rows")
                    plt.xticks(rotation=45, ha="right")
                    plt.tight_layout()
                    plt.savefig(figures_dir / "ai_category_distribution.svg", dpi=180)
                    plt.savefig(figures_dir / "ai_generated_category_distribution.svg", dpi=180)
                    plt.close()

    write_json(reports_dir / "eda_summary.json", summary)


def tokenize_with_keras(exp_dir: Path, max_tokens: int = 30000, max_length: int = 256) -> None:
    from tensorflow.keras.preprocessing.sequence import pad_sequences
    from tensorflow.keras.preprocessing.text import Tokenizer

    data_dir = exp_dir / "data"
    train_df = pd.read_csv(data_dir / "clean_train.csv", keep_default_na=False)
    tokenizer = Tokenizer(num_words=max_tokens, oov_token="<OOV>")
    tokenizer.fit_on_texts(train_df["Text"].astype(str).tolist())

    metadata = {
        "tokenizer": tokenizer,
        "max_tokens": max_tokens,
        "max_length": max_length,
        "framework": "tensorflow.keras.preprocessing.text.Tokenizer",
    }
    joblib.dump(metadata, data_dir / "tokenizer.joblib")

    for split in ["train", "val", "test"]:
        df = pd.read_csv(data_dir / f"clean_{split}.csv", keep_default_na=False)
        sequences = tokenizer.texts_to_sequences(df["Text"].astype(str).tolist())
        padded = pad_sequences(sequences, maxlen=max_length, padding="post", truncating="post")
        payload = {
            "input_ids": padded,
            "labels": df["Label"].astype(str).to_numpy(),
            "max_length": max_length,
        }
        joblib.dump(payload, data_dir / f"{split}_tok.pkl")


def metric_payload(y_true: np.ndarray, y_pred: np.ndarray, labels: list[str]) -> dict[str, float]:
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    return {
        "accuracy": float(report["accuracy"]),
        "precision": float(report["weighted avg"]["precision"]),
        "recall": float(report["weighted avg"]["recall"]),
        "f1": float(report["weighted avg"]["f1-score"]),
        "macro_f1": float(report["macro avg"]["f1-score"]),
    }


def save_dl_outputs(
    exp_dir: Path,
    family: str,
    model_name: str,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    label_names: list[str],
    history: tf.keras.callbacks.History,
    model: tf.keras.Model,
    y_score: np.ndarray | None = None,
) -> dict[str, object]:
    model_dir = exp_dir / "models" / family
    reports_dir = exp_dir / "evaluation" / "reports"
    figures_dir = exp_dir / "evaluation" / "figures"
    model_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    model.save(model_dir / f"{model_name}.keras")
    pd.DataFrame(history.history).to_csv(model_dir / f"{model_name}_training_log.csv", index=False)

    pd.DataFrame(classification_report(y_true, y_pred, labels=label_names, output_dict=True, zero_division=0)).transpose().to_csv(
        reports_dir / f"classification_report_{model_name}.csv",
        index_label="label",
    )
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

    roc_auc = None
    if y_score is not None and len(label_names) == 2 and len(np.unique(y_true)) == 2:
        positive_label = label_names[1]
        y_binary = np.array([1 if label == positive_label else 0 for label in y_true])
        roc_auc = float(roc_auc_score(y_binary, y_score))
        fpr, tpr, _thresholds = roc_curve(y_binary, y_score)
        pd.DataFrame({"fpr": fpr, "tpr": tpr}).to_csv(
            reports_dir / f"roc_curve_{model_name}.csv",
            index=False,
        )
        plt.figure(figsize=(5, 4))
        plt.plot(fpr, tpr, label=f"AUC = {roc_auc:.4f}")
        plt.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
        plt.title(f"ROC Curve: {model_name}")
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.legend(loc="lower right")
        plt.tight_layout()
        plt.savefig(figures_dir / f"roc_curve_{model_name}.svg", dpi=180)
        plt.close()

    row = {
        "experiment": exp_dir.name,
        "family": family,
        "model": model_name,
        "evaluation_train_rows": int(sum(len(joblib.load(exp_dir / "data" / f"{split}_tok.pkl")["labels"]) for split in ["train", "val"])),
        "test_rows": int(len(y_true)),
        "final_train_rows": int(sum(len(joblib.load(exp_dir / "data" / f"{split}_tok.pkl")["labels"]) for split in ["train", "val", "test"])),
        "saved_model_train_scope": "train_validation",
        **metric_payload(y_true, y_pred, label_names),
    }
    if roc_auc is not None:
        row["roc_auc"] = roc_auc
    return row


def train_bilstm(exp_dir: Path, label_names: list[str], seed: int) -> dict[str, object]:
    tf.keras.utils.set_random_seed(seed)
    data_dir = exp_dir / "data"
    tok_meta = joblib.load(data_dir / "tokenizer.joblib")
    max_tokens = int(tok_meta["max_tokens"])
    max_length = int(tok_meta["max_length"])
    label2id = {label: idx for idx, label in enumerate(label_names)}

    train = joblib.load(data_dir / "train_tok.pkl")
    val = joblib.load(data_dir / "val_tok.pkl")
    test = joblib.load(data_dir / "test_tok.pkl")
    x_train, y_train = train["input_ids"], np.array([label2id[label] for label in train["labels"]])
    x_val, y_val = val["input_ids"], np.array([label2id[label] for label in val["labels"]])
    x_test = test["input_ids"]
    y_test_labels = np.array(test["labels"])

    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(max_length,)),
            tf.keras.layers.Embedding(max_tokens, 64, mask_zero=True),
            tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(48)),
            tf.keras.layers.Dropout(0.35),
            tf.keras.layers.Dense(32, activation="relu"),
            tf.keras.layers.Dense(len(label_names), activation="softmax"),
        ]
    )
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        epochs=3,
        batch_size=64,
        verbose=2,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=1, restore_best_weights=True)],
    )
    probabilities = model.predict(x_test, batch_size=128, verbose=0)
    pred_ids = np.argmax(probabilities, axis=1)
    y_pred = np.array([label_names[idx] for idx in pred_ids])
    positive_scores = probabilities[:, 1] if probabilities.shape[1] == 2 else None
    return save_dl_outputs(exp_dir, "deep_learning", "BiLSTM_Keras", y_test_labels, y_pred, label_names, history, model, positive_scores)


from experiments.transformer_block import TransformerBlock  # noqa: F401, E402


def train_mini_transformer(exp_dir: Path, label_names: list[str], seed: int) -> dict[str, object]:
    tf.keras.utils.set_random_seed(seed)
    data_dir = exp_dir / "data"
    tok_meta = joblib.load(data_dir / "tokenizer.joblib")
    max_tokens = int(tok_meta["max_tokens"])
    max_length = int(tok_meta["max_length"])
    label2id = {label: idx for idx, label in enumerate(label_names)}

    train = joblib.load(data_dir / "train_tok.pkl")
    val = joblib.load(data_dir / "val_tok.pkl")
    test = joblib.load(data_dir / "test_tok.pkl")
    x_train, y_train = train["input_ids"], np.array([label2id[label] for label in train["labels"]])
    x_val, y_val = val["input_ids"], np.array([label2id[label] for label in val["labels"]])
    x_test = test["input_ids"]
    y_test_labels = np.array(test["labels"])

    inputs = tf.keras.layers.Input(shape=(max_length,))
    x = tf.keras.layers.Embedding(max_tokens, 64)(inputs)
    positions = tf.range(start=0, limit=max_length, delta=1)
    pos_embedding = tf.keras.layers.Embedding(input_dim=max_length, output_dim=64)(positions)
    x = x + pos_embedding
    x = TransformerBlock(embed_dim=64, num_heads=2, ff_dim=64)(x)
    x = tf.keras.layers.GlobalAveragePooling1D()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    outputs = tf.keras.layers.Dense(len(label_names), activation="softmax")(x)
    model = tf.keras.Model(inputs=inputs, outputs=outputs)
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        epochs=3,
        batch_size=64,
        verbose=2,
        callbacks=[tf.keras.callbacks.EarlyStopping(patience=1, restore_best_weights=True)],
    )
    probabilities = model.predict(x_test, batch_size=128, verbose=0)
    pred_ids = np.argmax(probabilities, axis=1)
    y_pred = np.array([label_names[idx] for idx in pred_ids])
    positive_scores = probabilities[:, 1] if probabilities.shape[1] == 2 else None
    return save_dl_outputs(exp_dir, "transformers", "MiniTransformer_Keras", y_test_labels, y_pred, label_names, history, model, positive_scores)


class TextDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer: AutoTokenizer, max_length: int):
        self.encodings = tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=max_length,
        )
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        item = {key: torch.tensor(value[idx]) for key, value in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


def train_xlmr(exp_dir: Path, label_names: list[str], seed: int, batch_size: int = 8) -> dict[str, object]:
    torch.manual_seed(seed)
    data_dir = exp_dir / "data"
    reports_dir = exp_dir / "evaluation" / "reports"
    figures_dir = exp_dir / "evaluation" / "figures"
    model_dir = exp_dir / "models" / "transformers" / "xlm-roberta-base"
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(data_dir / "clean_train.csv", keep_default_na=False)
    val_df = pd.read_csv(data_dir / "clean_val.csv", keep_default_na=False)
    test_df = pd.read_csv(data_dir / "clean_test.csv", keep_default_na=False)
    train_fit_df = pd.concat([train_df, val_df], ignore_index=True)

    label2id = {label: idx for idx, label in enumerate(label_names)}
    id2label = {idx: label for label, idx in label2id.items()}
    tokenizer = AutoTokenizer.from_pretrained("xlm-roberta-base")
    model = AutoModelForSequenceClassification.from_pretrained(
        "xlm-roberta-base",
        num_labels=len(label_names),
        id2label=id2label,
        label2id=label2id,
    )

    # CPU-friendly fine-tuning: train classifier and the last encoder block.
    for param in model.roberta.parameters():
        param.requires_grad = False
    for param in model.roberta.encoder.layer[-1].parameters():
        param.requires_grad = True
    for param in model.classifier.parameters():
        param.requires_grad = True

    max_length = 128
    train_dataset = TextDataset(
        train_fit_df["Text"].astype(str).tolist(),
        [label2id[label] for label in train_fit_df["Label"].astype(str).tolist()],
        tokenizer,
        max_length=max_length,
    )
    test_texts = test_df["Text"].astype(str).tolist()
    test_labels = test_df["Label"].astype(str).tolist()
    test_dataset = TextDataset(
        test_texts,
        [label2id[label] for label in test_labels],
        tokenizer,
        max_length=max_length,
    )

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=16)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=2e-5)
    model.train()
    losses: list[float] = []
    for epoch in range(1):
        for batch_idx, batch in enumerate(train_loader, start=1):
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            if batch_idx % 100 == 0:
                print(f"== {exp_dir.name}: XLM-R batch {batch_idx}/{len(train_loader)} loss={losses[-1]:.4f} ==")

    model.eval()
    pred_ids: list[int] = []
    positive_scores: list[float] = []
    with torch.no_grad():
        for batch in test_loader:
            labels_tensor = batch.pop("labels")
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits
            if len(label_names) == 2:
                positive_scores.extend(torch.softmax(logits, dim=-1)[:, 1].cpu().tolist())
            pred_ids.extend(torch.argmax(logits, dim=-1).cpu().tolist())
    y_pred = np.array([id2label[idx] for idx in pred_ids])
    y_true = np.array(test_labels)

    saved_model_dir = save_hf_model_with_fallback(model, tokenizer, model_dir)
    pd.DataFrame({"loss": losses}).to_csv(saved_model_dir / "xlm_roberta_training_log.csv", index=False)

    model_name = "XLMRoberta_FineTuned"
    pd.DataFrame(classification_report(y_true, y_pred, labels=label_names, output_dict=True, zero_division=0)).transpose().to_csv(
        reports_dir / f"classification_report_{model_name}.csv",
        index_label="label",
    )
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

    roc_auc = None
    if positive_scores and len(label_names) == 2 and len(np.unique(y_true)) == 2:
        y_binary = np.array([1 if label == label_names[1] else 0 for label in y_true])
        roc_auc = float(roc_auc_score(y_binary, np.array(positive_scores)))
        fpr, tpr, _thresholds = roc_curve(y_binary, np.array(positive_scores))
        pd.DataFrame({"fpr": fpr, "tpr": tpr}).to_csv(
            reports_dir / f"roc_curve_{model_name}.csv",
            index=False,
        )
        plt.figure(figsize=(5, 4))
        plt.plot(fpr, tpr, label=f"AUC = {roc_auc:.4f}")
        plt.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
        plt.title(f"ROC Curve: {model_name}")
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.legend(loc="lower right")
        plt.tight_layout()
        plt.savefig(figures_dir / f"roc_curve_{model_name}.svg", dpi=180)
        plt.close()

    row = {
        "experiment": exp_dir.name,
        "family": "transformers",
        "model": model_name,
        "evaluation_train_rows": int(len(train_fit_df)),
        "test_rows": int(len(test_df)),
        "final_train_rows": int(len(train_fit_df)),
        "saved_model_train_scope": "train_validation",
        **metric_payload(y_true, y_pred, label_names),
    }
    if roc_auc is not None:
        row["roc_auc"] = roc_auc
    return row


def write_step_report(exp_dir: Path, rows: list[dict[str, object]]) -> None:
    reports_dir = exp_dir / "evaluation" / "reports"
    results_dir = exp_dir / "results"
    reports_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    all_metrics = pd.DataFrame(rows).sort_values(["f1", "accuracy"], ascending=False)
    all_metrics.to_csv(reports_dir / "step9_metrics.csv", index=False)
    all_metrics.to_csv(results_dir / "all_models_comparison.csv", index=False)
    best = all_metrics.iloc[0]
    (results_dir / "best_model_summary.md").write_text(
        "# Best Model Summary\n\n"
        f"- experiment: {best['experiment']}\n"
        f"- family: {best['family']}\n"
        f"- model: {best['model']}\n"
        f"- accuracy: {best['accuracy']:.4f}\n"
        f"- precision: {best['precision']:.4f}\n"
        f"- recall: {best['recall']:.4f}\n"
        f"- f1: {best['f1']:.4f}\n"
        f"- macro_f1: {best['macro_f1']:.4f}\n\n"
        "Source: `results/all_models_comparison.csv`.\n",
        encoding="utf-8",
    )
    write_json(
        reports_dir / "step9_summary.json",
        {
            "best_model": best.to_dict(),
            "model_count": int(len(all_metrics)),
            "models": all_metrics["model"].tolist(),
        },
    )


def write_run_summary(all_rows: list[dict[str, object]], dataset_summary: dict[str, object]) -> None:
    comparison = pd.DataFrame(all_rows).sort_values(["f1", "accuracy"], ascending=False)
    for name, _remove_stopwords, _description in EXPERIMENTS:
        results_dir = ROOT / "experiments" / name / "results"
        comparison.to_csv(results_dir / "two_experiment_model_comparison.csv", index=False)
    write_json(
        ROOT / "experiments" / "full_12_step_run_summary.json",
        {
            "dataset": dataset_summary,
            "best_overall": comparison.iloc[0].to_dict(),
            "model_rows": comparison.to_dict(orient="records"),
            "pretrained_transformer_note": (
                "XLM-R was fine-tuned with CPU-friendly settings: classifier head and final encoder block trainable, "
                "one epoch, max_length=128. A lightweight Keras transformer was also trained from scratch."
            ),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the complete project pipeline.")
    parser.add_argument(
        "--only-experiment",
        choices=[name for name, _remove_stopwords, _description in EXPERIMENTS],
        default=None,
        help="Run a single experiment folder when resuming a long run.",
    )
    parser.add_argument(
        "--skip-xlm-r",
        action="store_true",
        help="Skip XLM-R fine-tuning.",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run GridSearchCV for traditional ML models.",
    )
    args = parser.parse_args()

    cfg = load_config(ROOT / "config.yaml")
    seed = int(cfg.get("project", {}).get("seed", 42))
    raw_path = resolve_path(ROOT, cfg["data"]["dataset_labeled"])
    raw_df = load_table(raw_path)
    compute_inter_annotator_agreement(raw_df, ROOT / "docs")
    dataset_df, dataset_summary = build_experiment_dataset(raw_df, seed, task="label", sampling="full")
    train_df, val_df, test_df = stratified_split_by_source(
        dataset_df,
        seed=seed,
        train_ratio=float(cfg["split"]["train_ratio"]),
        val_ratio=float(cfg["split"]["val_ratio"]),
    )
    label_names = sorted(dataset_df["Label"].unique().tolist())
    labels = LabelSpec(label2id={label: idx for idx, label in enumerate(label_names)})

    all_rows: list[dict[str, object]] = []
    experiment_summaries: dict[str, object] = {}
    selected_experiments = [
        item for item in EXPERIMENTS if args.only_experiment is None or item[0] == args.only_experiment
    ]
    for name, remove_stopwords, description in selected_experiments:
        exp_dir = ROOT / "experiments" / name
        exp_dir.mkdir(parents=True, exist_ok=True)
        split_summary = write_split_files(exp_dir, train_df, val_df, test_df, remove_stopwords)
        data_dir = exp_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        experiment_df = dataset_df.copy()
        if remove_stopwords:
            experiment_df["Text"] = experiment_df["Text"].map(remove_function_words)
        experiment_df.to_csv(data_dir / "full_labeled_dataset.csv", index=False)
        experiment_df.to_csv(data_dir / "balanced_labeled_dataset.csv", index=False)
        config_path = write_experiment_config(ROOT, cfg, exp_dir)
        experiment_summaries[name] = {
            "description": description,
            "config": str(config_path.relative_to(ROOT)),
            "splits": split_summary,
        }

        print(f"== {name}: STEP 4 EDA ==")
        generate_eda(exp_dir)
        print(f"== {name}: STEP 7 tokenization ==")
        tokenize_with_keras(exp_dir)
        print(f"== {name}: STEP 5 traditional ML ==")
        rows = train_traditional_models(
            exp_dir,
            seed,
            labels,
            include_xgboost=True,
            include_random_forest=True,
            tune=args.tune,
        )
        print(f"== {name}: STEP 6 BiLSTM ==")
        rows.append(train_bilstm(exp_dir, label_names, seed))
        print(f"== {name}: STEP 8 MiniTransformer ==")
        rows.append(train_mini_transformer(exp_dir, label_names, seed))
        if not args.skip_xlm_r:
            print(f"== {name}: STEP 8 XLM-R fine-tuning ==")
            rows.append(train_xlmr(exp_dir, label_names, seed))
        write_step_report(exp_dir, rows)
        generate_xai_outputs(exp_dir, "LinearSVC_TFIDF", labels)
        generate_xai_outputs_strict(exp_dir, "LinearSVC_TFIDF", labels)
        all_rows.extend(rows)

        write_json(
            exp_dir / "results" / "experiment_summary.json",
            {"dataset": dataset_summary, "experiment": experiment_summaries[name]},
        )

    if args.only_experiment is None:
        write_run_summary(all_rows, dataset_summary)
    else:
        existing_rows: list[dict[str, object]] = []
        for name, _remove_stopwords, _description in EXPERIMENTS:
            metrics_path = ROOT / "experiments" / name / "results" / "all_models_comparison.csv"
            if metrics_path.exists():
                existing_rows.extend(pd.read_csv(metrics_path).to_dict(orient="records"))
        write_run_summary(existing_rows, dataset_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
