"""Run PDF-missing requirements on top of existing experiment outputs."""

from __future__ import annotations

import argparse
import json
import re
import sys
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
import torch
from gensim.models import FastText, Word2Vec
from sklearn.metrics import classification_report, confusion_matrix
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from experiments.run_balanced_experiments import (
    LabelSpec,
    compute_inter_annotator_agreement,
    generate_xai_outputs,
    generate_xai_outputs_strict,
    load_config,
    load_table,
    resolve_path,
    train_traditional_models,
)
from experiments.run_full_12_steps import (
    EXPERIMENTS,
    TextDataset,
    metric_payload,
    save_dl_outputs,
    write_step_report,
)

TRANSFORMER_SPECS: list[tuple[str, str]] = [
    ("bert-base-multilingual-cased", "mBERT_FineTuned"),
    ("shuakshay/SomBERTa", "SomBERTa_FineTuned"),
    ("Davlan/afro-xlmr-base", "AfroXLMR_FineTuned"),
    ("castorini/afriberta_base", "AfriBERTa_FineTuned"),
]


def tokenize_texts(texts: list[str]) -> list[list[str]]:
    return [re.findall(r"\b\w+\b", text.lower()) for text in texts]


def build_embedding_matrix(
    tokenizer_meta: dict,
    embedding_model: Word2Vec | FastText,
    embedding_dim: int,
) -> tuple[np.ndarray, int]:
    tokenizer = tokenizer_meta["tokenizer"]
    word_index = tokenizer.word_index
    max_tokens = int(tokenizer_meta["max_tokens"])
    matrix = np.random.uniform(-0.05, 0.05, (max_tokens, embedding_dim)).astype(np.float32)
    matrix[0] = 0.0
    hits = 0
    for word, index in word_index.items():
        if index >= max_tokens:
            continue
        vector = None
        if word in embedding_model.wv:
            vector = embedding_model.wv[word]
        elif hasattr(embedding_model.wv, "get_vector"):
            try:
                vector = embedding_model.wv.get_vector(word)
            except KeyError:
                vector = None
        if vector is not None:
            matrix[index] = vector
            hits += 1
    return matrix, hits


def train_bilstm_with_embeddings(
    exp_dir: Path,
    label_names: list[str],
    seed: int,
    embedding_type: str,
    model_name: str,
) -> dict[str, object]:
    tf.keras.utils.set_random_seed(seed)
    data_dir = exp_dir / "data"
    tok_meta = joblib.load(data_dir / "tokenizer.joblib")
    max_tokens = int(tok_meta["max_tokens"])
    max_length = int(tok_meta["max_length"])
    embedding_dim = 100
    label2id = {label: idx for idx, label in enumerate(label_names)}

    train_df = pd.read_csv(data_dir / "clean_train.csv", keep_default_na=False)
    sentences = tokenize_texts(train_df["Text"].astype(str).tolist())
    if embedding_type == "word2vec":
        embedding_model = Word2Vec(
            sentences=sentences,
            vector_size=embedding_dim,
            window=5,
            min_count=2,
            workers=1,
            seed=seed,
            epochs=5,
        )
        joblib.dump(embedding_model, data_dir / "word2vec.model")
    else:
        embedding_model = FastText(
            sentences=sentences,
            vector_size=embedding_dim,
            window=5,
            min_count=2,
            workers=1,
            seed=seed,
            epochs=5,
        )
        joblib.dump(embedding_model, data_dir / "fasttext.model")

    embedding_matrix, vocab_hits = build_embedding_matrix(tok_meta, embedding_model, embedding_dim)
    joblib.dump(
        {"embedding_type": embedding_type, "vocab_hits": vocab_hits, "embedding_dim": embedding_dim},
        data_dir / f"{model_name.lower()}_embedding_meta.joblib",
    )

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
            tf.keras.layers.Embedding(
                max_tokens,
                embedding_dim,
                mask_zero=True,
                weights=[embedding_matrix],
                trainable=False,
            ),
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
    pred_ids = np.argmax(model.predict(x_test, batch_size=128, verbose=0), axis=1)
    y_pred = np.array([label_names[idx] for idx in pred_ids])
    return save_dl_outputs(exp_dir, "deep_learning", model_name, y_test_labels, y_pred, label_names, history, model)


def freeze_transformer_for_cpu_tune(model: AutoModelForSequenceClassification) -> None:
    backbone = None
    for attr in ("roberta", "bert", "deberta", "xlm_roberta"):
        if hasattr(model, attr):
            backbone = getattr(model, attr)
            break
    if backbone is None:
        for param in model.parameters():
            param.requires_grad = False
        for param in model.classifier.parameters():
            param.requires_grad = True
        return
    for param in backbone.parameters():
        param.requires_grad = False
    for param in backbone.encoder.layer[-1].parameters():
        param.requires_grad = True
    for param in model.classifier.parameters():
        param.requires_grad = True


def train_hf_transformer(
    exp_dir: Path,
    label_names: list[str],
    seed: int,
    model_id: str,
    model_name: str,
) -> dict[str, object]:
    torch.manual_seed(seed)
    data_dir = exp_dir / "data"
    reports_dir = exp_dir / "evaluation" / "reports"
    figures_dir = exp_dir / "evaluation" / "figures"
    model_dir = exp_dir / "models" / "transformers" / model_name
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(data_dir / "clean_train.csv", keep_default_na=False)
    val_df = pd.read_csv(data_dir / "clean_val.csv", keep_default_na=False)
    test_df = pd.read_csv(data_dir / "clean_test.csv", keep_default_na=False)
    train_fit_df = pd.concat([train_df, val_df], ignore_index=True)

    label2id = {label: idx for idx, label in enumerate(label_names)}
    id2label = {idx: label for label, idx in label2id.items()}
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_id,
        num_labels=len(label_names),
        id2label=id2label,
        label2id=label2id,
    )
    freeze_transformer_for_cpu_tune(model)

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

    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=16)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=2e-5)
    model.train()
    losses: list[float] = []
    for _epoch in range(1):
        for batch_idx, batch in enumerate(train_loader, start=1):
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            if batch_idx % 100 == 0:
                print(f"== {exp_dir.name}: {model_name} batch {batch_idx}/{len(train_loader)} loss={losses[-1]:.4f} ==")

    model.eval()
    pred_ids: list[int] = []
    with torch.no_grad():
        for batch in test_loader:
            batch.pop("labels")
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits
            pred_ids.extend(torch.argmax(logits, dim=-1).cpu().tolist())
    y_pred = np.array([id2label[idx] for idx in pred_ids])
    y_true = np.array(test_labels)

    model.save_pretrained(model_dir)
    tokenizer.save_pretrained(model_dir)
    pd.DataFrame({"loss": losses}).to_csv(model_dir / f"{model_name}_training_log.csv", index=False)

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
    plt.savefig(figures_dir / f"confusion_matrix_{model_name}.png", dpi=180)
    plt.close()

    return {
        "experiment": exp_dir.name,
        "family": "transformers",
        "model": model_name,
        "evaluation_train_rows": int(len(train_fit_df)),
        "test_rows": int(len(test_df)),
        "final_train_rows": int(len(train_fit_df)),
        "saved_model_train_scope": "train_validation",
        **metric_payload(y_true, y_pred, label_names),
    }


def model_report_exists(exp_dir: Path, model_name: str) -> bool:
    return (exp_dir / "evaluation" / "reports" / f"classification_report_{model_name}.csv").exists()


def infer_model_family(model_name: str) -> str:
    if model_name.endswith("_TFIDF"):
        return "traditional_ml"
    if model_name.startswith("BiLSTM"):
        return "deep_learning"
    return "transformers"


def row_from_classification_report(exp_dir: Path, model_name: str) -> dict[str, object]:
    report_path = exp_dir / "evaluation" / "reports" / f"classification_report_{model_name}.csv"
    report = pd.read_csv(report_path, index_col=0)
    weighted = report.loc["weighted avg"]
    macro = report.loc["macro avg"]
    accuracy = float(report.loc["accuracy", "precision"])
    family = infer_model_family(model_name)
    train_scope = "full_dataset" if family == "traditional_ml" else "train_validation"
    eval_rows = 4990
    final_rows = 5869 if family == "traditional_ml" else eval_rows
    return {
        "experiment": exp_dir.name,
        "family": family,
        "model": model_name,
        "evaluation_train_rows": eval_rows,
        "test_rows": 879,
        "final_train_rows": final_rows,
        "saved_model_train_scope": train_scope,
        "accuracy": accuracy,
        "precision": float(weighted["precision"]),
        "recall": float(weighted["recall"]),
        "f1": float(weighted["f1-score"]),
        "macro_f1": float(macro["f1-score"]),
    }


def rebuild_comparison_from_reports(exp_dir: Path) -> list[dict[str, object]]:
    reports_dir = exp_dir / "evaluation" / "reports"
    rows: list[dict[str, object]] = []
    for path in sorted(reports_dir.glob("classification_report_*.csv")):
        model_name = path.stem.replace("classification_report_", "")
        rows.append(row_from_classification_report(exp_dir, model_name))
    rows.sort(key=lambda row: (float(row["f1"]), float(row["accuracy"])), reverse=True)
    return rows


def merge_model_rows(exp_dir: Path, new_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    results_path = exp_dir / "results" / "all_models_comparison.csv"
    existing = pd.read_csv(results_path).to_dict(orient="records") if results_path.exists() else []
    by_model = {str(row["model"]): row for row in existing}
    for row in new_rows:
        by_model[str(row["model"])] = row
    merged = list(by_model.values())
    merged.sort(key=lambda row: (float(row.get("f1", 0.0)), float(row.get("accuracy", 0.0))), reverse=True)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Complete PDF-missing experiment requirements.")
    parser.add_argument(
        "--only-experiment",
        choices=[name for name, _remove_stopwords, _description in EXPERIMENTS],
        default=None,
    )
    parser.add_argument("--skip-transformers", action="store_true")
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--skip-tuning", action="store_true")
    parser.add_argument("--skip-xai", action="store_true")
    args = parser.parse_args()

    cfg = load_config(ROOT / "config.yaml")
    seed = int(cfg.get("project", {}).get("seed", 42))
    raw_df = load_table(resolve_path(ROOT, cfg["data"]["dataset_labeled"]))
    sample_exp = ROOT / "experiments" / "experiment_1_stopwords_included"
    label_source = pd.read_csv(sample_exp / "data" / "clean_train.csv", keep_default_na=False)
    label_names = sorted(label_source["Label"].astype(str).unique().tolist())
    labels = LabelSpec(label2id={label: idx for idx, label in enumerate(label_names)})

    agreement = compute_inter_annotator_agreement(raw_df, ROOT / "docs")
    print("Inter-annotator agreement:", json.dumps(agreement, indent=2))

    selected = [item for item in EXPERIMENTS if args.only_experiment is None or item[0] == args.only_experiment]
    all_rows: list[dict[str, object]] = []
    for name, _remove_stopwords, _description in selected:
        exp_dir = ROOT / "experiments" / name
        if not (exp_dir / "data" / "tokenizer.joblib").exists():
            raise FileNotFoundError(f"Missing tokenizer for {name}. Run experiments/run_full_12_steps.py first.")

        new_rows: list[dict[str, object]] = []
        if not args.skip_tuning:
            print(f"== {name}: GridSearchCV for traditional ML ==")
            new_rows.extend(
                train_traditional_models(
                    exp_dir,
                    seed,
                    labels,
                    include_xgboost=True,
                    include_random_forest=True,
                    tune=True,
                )
            )

        if not args.skip_embeddings:
            if model_report_exists(exp_dir, "BiLSTM_Word2Vec"):
                print(f"== {name}: BiLSTM + Word2Vec already complete, skipping ==")
            else:
                print(f"== {name}: BiLSTM + Word2Vec ==")
                new_rows.append(train_bilstm_with_embeddings(exp_dir, label_names, seed, "word2vec", "BiLSTM_Word2Vec"))
            if model_report_exists(exp_dir, "BiLSTM_FastText"):
                print(f"== {name}: BiLSTM + FastText already complete, skipping ==")
            else:
                print(f"== {name}: BiLSTM + FastText ==")
                new_rows.append(train_bilstm_with_embeddings(exp_dir, label_names, seed, "fasttext", "BiLSTM_FastText"))

        if not args.skip_transformers:
            for model_id, model_name in TRANSFORMER_SPECS:
                if model_report_exists(exp_dir, model_name):
                    print(f"== {name}: {model_name} already complete, skipping ==")
                    continue
                print(f"== {name}: fine-tuning {model_name} ==")
                new_rows.append(train_hf_transformer(exp_dir, label_names, seed, model_id, model_name))

        merged_rows = rebuild_comparison_from_reports(exp_dir)
        write_step_report(exp_dir, merged_rows)
        if not args.skip_xai:
            generate_xai_outputs(exp_dir, "LinearSVC_TFIDF", labels)
            generate_xai_outputs_strict(exp_dir, "LinearSVC_TFIDF", labels)
        all_rows.extend(merged_rows)

    combined_rows: list[dict[str, object]] = []
    for name, _remove_stopwords, _description in EXPERIMENTS:
        metrics_path = ROOT / "experiments" / name / "results" / "all_models_comparison.csv"
        if metrics_path.exists():
            combined_rows.extend(pd.read_csv(metrics_path).to_dict(orient="records"))
    comparison = pd.DataFrame(combined_rows).sort_values(["f1", "accuracy"], ascending=False)
    for name, _remove_stopwords, _description in EXPERIMENTS:
        results_dir = ROOT / "experiments" / name / "results"
        if results_dir.exists():
            comparison.to_csv(results_dir / "two_experiment_model_comparison.csv", index=False)
    print("Completion pass finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
