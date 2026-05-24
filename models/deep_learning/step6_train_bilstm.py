"""
STEP 6 trainer:
- BiLSTM + FastText
- BiLSTM + Word2Vec

Outputs:
- models/deep_learning/training_logs/*.csv
- models/deep_learning/checkpoints/*.weights.h5
- models/deep_learning/model_comparison_metrics.csv
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yaml
from gensim.models import FastText, Word2Vec
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from tensorflow.keras.callbacks import CSVLogger, EarlyStopping, ModelCheckpoint
from tensorflow.keras.layers import Bidirectional, Dense, Dropout, Embedding, LSTM
from tensorflow.keras.models import Sequential
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.utils import set_random_seed


def find_project_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "config.yaml").exists():
            return p
    raise FileNotFoundError("config.yaml not found")


def resolve_path(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def load_config(config_path: Path) -> Dict:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def encode_labels(labels: pd.Series) -> np.ndarray:
    mapping = {"HUMAN": 0, "AI": 1, "0": 0, "1": 1}
    normalized = labels.astype(str).str.strip().str.upper()
    encoded = normalized.map(mapping)
    if encoded.isna().any():
        bad = sorted(set(normalized[encoded.isna()].tolist()))
        raise ValueError(f"Unknown labels found: {bad}")
    return encoded.astype(np.int32).to_numpy()


def prepare_data(
    project_root: Path, cfg: Dict
) -> Tuple[List[str], List[str], List[str], np.ndarray, np.ndarray, np.ndarray]:
    processed_dir = resolve_path(project_root, cfg["paths"]["data_processed_dir"])
    train_df = pd.read_csv(processed_dir / cfg["data"]["train_file"])
    val_df = pd.read_csv(processed_dir / cfg["data"]["val_file"])
    test_df = pd.read_csv(processed_dir / cfg["data"]["test_file"])

    text_col = cfg["data"]["text_column"]
    label_col = cfg["data"]["label_column"]

    required = [text_col, label_col]
    for name, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"{name} split missing columns: {missing}")

    x_train = train_df[text_col].astype(str).tolist()
    x_val = val_df[text_col].astype(str).tolist()
    x_test = test_df[text_col].astype(str).tolist()
    y_train = encode_labels(train_df[label_col])
    y_val = encode_labels(val_df[label_col])
    y_test = encode_labels(test_df[label_col])
    return x_train, x_val, x_test, y_train, y_val, y_test


def build_tokenizer(train_texts: List[str], max_tokens: int) -> Tokenizer:
    tokenizer = Tokenizer(num_words=max_tokens, oov_token="[OOV]", lower=False)
    tokenizer.fit_on_texts(train_texts)
    return tokenizer


def texts_to_sequences(
    tokenizer: Tokenizer, texts: List[str], max_len: int
) -> np.ndarray:
    seq = tokenizer.texts_to_sequences(texts)
    return pad_sequences(seq, maxlen=max_len, padding="post", truncating="post")


def train_embedding_vectors(
    sentences: List[List[str]], embedding_name: str, vector_size: int, seed: int
):
    common_kwargs = dict(
        vector_size=vector_size,
        window=5,
        min_count=2,
        workers=1,
        sg=1,
        seed=seed,
        epochs=10,
    )

    if embedding_name == "fasttext":
        model = FastText(sentences=sentences, **common_kwargs)
    elif embedding_name == "word2vec":
        model = Word2Vec(sentences=sentences, **common_kwargs)
    else:
        raise ValueError(f"Unsupported embedding_name: {embedding_name}")
    return model.wv


def build_embedding_matrix(
    tokenizer: Tokenizer,
    keyed_vectors,
    max_tokens: int,
    embedding_dim: int,
    seed: int,
) -> np.ndarray:
    vocab_size = min(max_tokens, len(tokenizer.word_index) + 1)
    rng = np.random.default_rng(seed)
    matrix = rng.normal(0.0, 0.05, size=(vocab_size, embedding_dim)).astype(np.float32)
    matrix[0] = 0.0

    for word, idx in tokenizer.word_index.items():
        if idx >= vocab_size:
            continue
        if word in keyed_vectors:
            matrix[idx] = keyed_vectors[word]
    return matrix


def build_bilstm_model(
    vocab_size: int, embedding_matrix: np.ndarray, cfg_dl: Dict, max_len: int
) -> Sequential:
    model = Sequential(
        [
            Embedding(
                input_dim=vocab_size,
                output_dim=int(cfg_dl["embedding_dim"]),
                weights=[embedding_matrix],
                input_length=max_len,
                trainable=bool(cfg_dl["trainable_embeddings"]),
            ),
            Bidirectional(
                LSTM(
                    int(cfg_dl["lstm_units_1"]),
                    return_sequences=True,
                    dropout=0.2,
                )
            ),
            Dropout(float(cfg_dl["dropout_1"])),
            Bidirectional(LSTM(int(cfg_dl["lstm_units_2"]), dropout=0.2)),
            Dropout(float(cfg_dl["dropout_2"])),
            Dense(int(cfg_dl["dense_units"]), activation="relu"),
            Dense(1, activation="sigmoid"),
        ]
    )

    model.compile(
        optimizer=Adam(learning_rate=float(cfg_dl["learning_rate"])),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    return model


def train_and_evaluate(
    embedding_name: str,
    tokenizer: Tokenizer,
    x_train_text: List[str],
    x_val_text: List[str],
    x_test_text: List[str],
    y_train: np.ndarray,
    y_val: np.ndarray,
    y_test: np.ndarray,
    cfg_dl: Dict,
    max_len: int,
    logs_dir: Path,
    ckpt_dir: Path,
    seed: int,
) -> Dict[str, float]:
    sentences = [t.split() for t in x_train_text]
    vectors = train_embedding_vectors(
        sentences=sentences,
        embedding_name=embedding_name,
        vector_size=int(cfg_dl["embedding_dim"]),
        seed=seed,
    )

    emb_matrix = build_embedding_matrix(
        tokenizer=tokenizer,
        keyed_vectors=vectors,
        max_tokens=int(cfg_dl["max_tokens"]),
        embedding_dim=int(cfg_dl["embedding_dim"]),
        seed=seed,
    )
    vocab_size = emb_matrix.shape[0]

    x_train = texts_to_sequences(tokenizer, x_train_text, max_len)
    x_val = texts_to_sequences(tokenizer, x_val_text, max_len)
    x_test = texts_to_sequences(tokenizer, x_test_text, max_len)

    model = build_bilstm_model(
        vocab_size=vocab_size, embedding_matrix=emb_matrix, cfg_dl=cfg_dl, max_len=max_len
    )

    log_path = logs_dir / f"bilstm_{embedding_name}_training_log.csv"
    ckpt_path = ckpt_dir / f"bilstm_{embedding_name}_best.weights.h5"

    callbacks = [
        EarlyStopping(
            monitor="val_loss",
            patience=int(cfg_dl["patience"]),
            restore_best_weights=True,
        ),
        CSVLogger(log_path.as_posix(), append=False),
        ModelCheckpoint(
            filepath=ckpt_path.as_posix(),
            monitor="val_loss",
            save_best_only=True,
            save_weights_only=True,
            verbose=1,
        ),
    ]

    model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        epochs=int(cfg_dl["epochs"]),
        batch_size=int(cfg_dl["batch_size"]),
        callbacks=callbacks,
        verbose=1,
    )

    prob = model.predict(x_test, verbose=0).ravel()
    pred = (prob >= 0.5).astype(np.int32)

    acc = accuracy_score(y_test, pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, pred, average="binary", zero_division=0
    )

    return {
        "Model Name": f"BiLSTM + {embedding_name.capitalize()}",
        "Accuracy": f"{acc * 100:.2f}%",
        "Precision": float(precision),
        "Recall": float(recall),
        "F1-Score": float(f1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="STEP 6 BiLSTM trainer")
    parser.add_argument("--config", default="config.yaml", help="Path to config yaml")
    parser.add_argument(
        "--embedding",
        choices=["fasttext", "word2vec", "both"],
        default="both",
        help="Which embedding setup to run",
    )
    args = parser.parse_args()

    project_root = find_project_root(Path.cwd())
    config_path = resolve_path(project_root, args.config)
    cfg = load_config(config_path)

    seed = int(cfg["project"]["seed"])
    random.seed(seed)
    np.random.seed(seed)
    set_random_seed(seed)

    cfg_dl = {
        "max_tokens": 30000,
        "embedding_dim": 200,
        "lstm_units_1": 128,
        "lstm_units_2": 64,
        "dropout_1": 0.5,
        "dropout_2": 0.3,
        "dense_units": 64,
        "batch_size": 64,
        "epochs": 8,
        "patience": 2,
        "learning_rate": 0.001,
        "trainable_embeddings": False,
    }
    cfg_dl.update(cfg.get("deep_learning", {}))

    max_len = int(cfg.get("tokenization", {}).get("max_length", 256))

    logs_dir = resolve_path(project_root, cfg["paths"]["deep_learning_logs_dir"])
    ckpt_dir = resolve_path(project_root, cfg["paths"]["deep_learning_checkpoints_dir"])
    logs_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    x_train, x_val, x_test, y_train, y_val, y_test = prepare_data(project_root, cfg)
    tokenizer = build_tokenizer(x_train, max_tokens=int(cfg_dl["max_tokens"]))

    embeddings = ["fasttext", "word2vec"] if args.embedding == "both" else [args.embedding]
    rows = []
    for emb in embeddings:
        print(f"\n=== Training {emb} pipeline ===")
        row = train_and_evaluate(
            embedding_name=emb,
            tokenizer=tokenizer,
            x_train_text=x_train,
            x_val_text=x_val,
            x_test_text=x_test,
            y_train=y_train,
            y_val=y_val,
            y_test=y_test,
            cfg_dl=cfg_dl,
            max_len=max_len,
            logs_dir=logs_dir,
            ckpt_dir=ckpt_dir,
            seed=seed,
        )
        rows.append(row)
        print(row)

    df = pd.DataFrame(rows)
    out_csv = project_root / "models" / "deep_learning" / "model_comparison_metrics.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved comparison table: {out_csv}")


if __name__ == "__main__":
    main()

