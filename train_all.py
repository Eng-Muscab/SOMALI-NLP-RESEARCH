"""
Train ALL models for both experiments in one command.
Skips any model that is already trained (file exists).

Usage (from project root):
    python train_all.py

To force retrain a specific experiment:
    python train_all.py --force-exp experiment_1_stopwords_included

To force retrain everything:
    python train_all.py --force-all
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# ── project root on sys.path ─────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())

EXPERIMENTS = [
    "experiment_1_stopwords_included",
    "experiment_2_stopwords_removed",
]

TRADITIONAL_ML_MODELS = [
    "LinearSVC_TFIDF",
    "LogisticRegression_TFIDF",
    "RandomForest_TFIDF",
    "XGBoost_TFIDF",
]


def _joblib_exists(exp_dir: Path, model_name: str) -> bool:
    return (exp_dir / "models" / "traditional_ml" / f"{model_name}.joblib").exists()


def _keras_exists(exp_dir: Path, subfolder: str, model_name: str) -> bool:
    return (exp_dir / "models" / subfolder / f"{model_name}.keras").exists()


def _tok_exists(exp_dir: Path) -> bool:
    return (exp_dir / "data" / "tokenizer.joblib").exists()


def _emb_exists(exp_dir: Path, emb_type: str) -> bool:
    return (exp_dir / "data" / f"{emb_type}.model").exists()


def step(msg: str) -> None:
    print(f"\n  >> {msg}")


def train_traditional(exp_dir: Path, seed: int, force: bool) -> None:
    missing = [m for m in TRADITIONAL_ML_MODELS if not _joblib_exists(exp_dir, m)]
    if not force and not missing:
        print("  [SKIP] All traditional ML models already exist.")
        return

    targets = TRADITIONAL_ML_MODELS if force else missing
    print(f"  Training: {', '.join(targets)}")

    import pandas as pd
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer, FeatureUnion
    from sklearn.pipeline import Pipeline
    from sklearn.svm import LinearSVC
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score, classification_report
    import numpy as np

    data_dir = exp_dir / "data"
    model_dir = exp_dir / "models" / "traditional_ml"
    reports_dir = exp_dir / "evaluation" / "reports"
    figures_dir = exp_dir / "evaluation" / "figures"
    model_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    train_df = pd.read_csv(data_dir / "clean_train.csv", keep_default_na=False)
    val_df   = pd.read_csv(data_dir / "clean_val.csv",   keep_default_na=False)
    test_df  = pd.read_csv(data_dir / "clean_test.csv",  keep_default_na=False)
    for df in (train_df, val_df, test_df):
        df["Text"] = df["Text"].fillna("").astype(str).str.strip()
        df.drop(df[df["Text"].str.len() == 0].index, inplace=True)

    train_fit_df = pd.concat([train_df, val_df], ignore_index=True)
    final_fit_df = pd.concat([train_df, val_df, test_df], ignore_index=True)
    label2id = {"AI": 0, "HUMAN": 1}

    x_test  = test_df["Text"].astype(str).tolist()
    y_test  = test_df["Label"].map(label2id).to_numpy(dtype=int)
    x_train = train_fit_df["Text"].astype(str).tolist()
    y_train = train_fit_df["Label"].map(label2id).to_numpy(dtype=int)
    x_final = final_fit_df["Text"].astype(str).tolist()
    y_final = final_fit_df["Label"].map(label2id).to_numpy(dtype=int)

    tfidf_union = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2),
                                 max_features=12000, sublinear_tf=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                 max_features=12000, sublinear_tf=True)),
    ])

    specs = {
        "LinearSVC_TFIDF": Pipeline([("tfidf", tfidf_union),
                                     ("clf", LinearSVC(C=1.0, class_weight="balanced", max_iter=2000))]),
        "LogisticRegression_TFIDF": Pipeline([("tfidf", tfidf_union),
                                              ("clf", LogisticRegression(C=1.0, class_weight="balanced",
                                                                         max_iter=2000, solver="lbfgs"))]),
        "RandomForest_TFIDF": Pipeline([
            ("tfidf", TfidfVectorizer(analyzer="word", ngram_range=(1, 2),
                                     max_features=10000, sublinear_tf=True)),
            ("clf", RandomForestClassifier(n_estimators=120, class_weight="balanced",
                                           random_state=seed, n_jobs=-1)),
        ]),
    }

    try:
        from xgboost import XGBClassifier
        specs["XGBoost_TFIDF"] = Pipeline([
            ("tfidf", TfidfVectorizer(analyzer="word", ngram_range=(1, 2),
                                     max_features=15000, sublinear_tf=True)),
            ("clf", XGBClassifier(random_state=seed, eval_metric="logloss",
                                  use_label_encoder=False)),
        ])
    except ImportError:
        print("  [WARN] XGBoost not installed — skipping XGBoost_TFIDF")

    label_names = ["AI", "HUMAN"]
    for name in targets:
        if name not in specs:
            continue
        t0 = time.time()
        pipe = specs[name]
        pipe.fit(x_train, y_train)
        y_pred = pipe.predict(x_test)
        acc = accuracy_score(y_test, y_pred)
        f1  = f1_score(y_test, y_pred, average="weighted")
        # Final fit on train+val+test before saving
        pipe.fit(x_final, y_final)
        out_path = model_dir / f"{name}.joblib"
        joblib.dump(pipe, out_path)
        # Save classification report
        report = classification_report(y_test, pipe.predict(x_test), target_names=label_names)
        (reports_dir / f"classification_report_{name}.txt").write_text(report, encoding="utf-8")
        elapsed = time.time() - t0
        print(f"  [OK]{name}  acc={acc:.4f}  f1={f1:.4f}  ({elapsed:.0f}s)  → {out_path.name}")


def train_keras_models(exp_dir: Path, force: bool) -> None:
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    from experiments.train_deep_learning import main as _dl_main
    from experiments.run_full_12_steps import (
        tokenize_with_keras, train_bilstm, train_mini_transformer,
    )

    label_names = ["AI", "HUMAN"]
    seed = 42
    data_dir = exp_dir / "data"

    # Tokenizer
    tok_file = data_dir / "tokenizer.joblib"
    if force or not tok_file.exists():
        print("  [RUN] Building Keras tokenizer …")
        tokenize_with_keras(exp_dir, max_tokens=30_000, max_length=256)
    else:
        print("  [SKIP] tokenizer.joblib already exists.")

    # BiLSTM_Keras
    bilstm_path = exp_dir / "models" / "deep_learning" / "BiLSTM_Keras.keras"
    if force or not bilstm_path.exists():
        print("  [RUN] Training BiLSTM_Keras …")
        m = train_bilstm(exp_dir, label_names, seed)
        print(f"        acc={m.get('accuracy',0):.4f}  f1={m.get('f1',0):.4f}")
    else:
        print("  [SKIP] BiLSTM_Keras.keras already exists.")

    # MiniTransformer_Keras
    mini_path = exp_dir / "models" / "transformers" / "MiniTransformer_Keras.keras"
    if force or not mini_path.exists():
        print("  [RUN] Training MiniTransformer_Keras …")
        m = train_mini_transformer(exp_dir, label_names, seed)
        print(f"        acc={m.get('accuracy',0):.4f}  f1={m.get('f1',0):.4f}")
    else:
        print("  [SKIP] MiniTransformer_Keras.keras already exists.")


def train_embedding_models(exp_dir: Path, force: bool) -> None:
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    from experiments.run_completion_pass import train_bilstm_with_embeddings, keras_artifact_exists

    label_names = ["AI", "HUMAN"]
    seed = 42

    for emb_type, model_name in [("word2vec", "BiLSTM_Word2Vec"), ("fasttext", "BiLSTM_FastText")]:
        exists = keras_artifact_exists(exp_dir, model_name)
        if not force and exists:
            print(f"  [SKIP] {model_name}.keras already exists.")
        else:
            print(f"  [RUN] Training {model_name} …")
            m = train_bilstm_with_embeddings(exp_dir, label_names, seed, emb_type, model_name)
            print(f"        acc={m.get('accuracy',0):.4f}  f1={m.get('f1',0):.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train all models for both experiments.")
    parser.add_argument("--force-all", action="store_true",
                        help="Retrain everything even if models already exist.")
    parser.add_argument("--force-exp", choices=EXPERIMENTS, default=None,
                        help="Force retrain for one specific experiment only.")
    parser.add_argument("--skip-traditional", action="store_true",
                        help="Skip traditional ML training.")
    parser.add_argument("--skip-deep", action="store_true",
                        help="Skip Keras deep learning training.")
    parser.add_argument("--skip-embedding", action="store_true",
                        help="Skip Word2Vec/FastText BiLSTM training.")
    args = parser.parse_args()

    total_start = time.time()
    print("\n" + "="*60)
    print("  SOMALI NLP - TRAIN ALL MODELS")
    print("="*60)
    print("  Models already trained will be SKIPPED automatically.")
    print("  Use --force-all to retrain everything from scratch.\n")

    for exp_name in EXPERIMENTS:
        exp_dir = ROOT / "experiments" / exp_name
        force = args.force_all or (args.force_exp == exp_name)

        print(f"\n{'='*60}")
        print(f"  EXPERIMENT: {exp_name}")
        print(f"{'='*60}")

        # ── 1. Traditional ML ─────────────────────────────────────
        if not args.skip_traditional:
            step("Traditional ML  (LinearSVC / LogReg / RandomForest / XGBoost)")
            train_traditional(exp_dir, seed=42, force=force)

        # ── 2. Keras BiLSTM + MiniTransformer ────────────────────
        if not args.skip_deep:
            step("Keras Deep Learning  (BiLSTM / MiniTransformer)")
            train_keras_models(exp_dir, force=force)

        # ── 3. Embedding BiLSTMs ──────────────────────────────────
        if not args.skip_embedding:
            step("Embedding BiLSTMs  (Word2Vec / FastText)")
            train_embedding_models(exp_dir, force=force)

    elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  ALL DONE in {elapsed/60:.1f} minutes")
    print(f"  Restart backend to load new models:")
    print(f"  -> Ctrl+C then re-run uvicorn")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
