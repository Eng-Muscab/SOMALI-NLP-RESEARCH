"""Retrain all 13 Experiment 2 models against the current stop-word list.

The individual trainers skip any model whose artifact already exists, which is what
you want when filling gaps and exactly wrong after the splits change -- every stale
Experiment 2 artifact has to go first or the run silently keeps yesterday's models.
This script clears them (into a backup directory), then drives every trainer in
order, and never touches Experiment 1.

Progress is recorded in `retrain_exp2_state.json` after each stage, so a crash or a
closed laptop resumes from the last finished stage instead of starting over:

    python experiments/retrain_exp2_all.py            # run / resume
    python experiments/retrain_exp2_all.py --restart  # ignore saved progress
    python experiments/retrain_exp2_all.py --only transformers

Expect roughly 10 hours on CPU; the five fine-tuned transformers are ~9 of them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXP = "experiment_2_stopwords_removed"
EXP_DIR = ROOT / "experiments" / EXP
STATE = ROOT / "experiments" / "retrain_exp2_state.json"
STALE_BACKUP = EXP_DIR / "_pre_483_models"
LABEL_NAMES = ["AI", "HUMAN"]
SEED = 42

# Artifacts whose presence makes a trainer skip, per stage.  Cleared just before the
# stage runs, so a stage that has already finished is never wiped by a later resume.
STALE = {
    "traditional": ["models/traditional_ml"],
    "keras": [
        "data/tokenizer.joblib",
        "data/train_tok.pkl",
        "data/val_tok.pkl",
        "data/test_tok.pkl",
        "models/deep_learning/BiLSTM_Keras.keras",
        "models/transformers/MiniTransformer_Keras.keras",
    ],
    "embeddings": [
        "data/word2vec.model",
        "data/fasttext.model",
        "data/bilstm_word2vec_embedding_meta.joblib",
        "data/bilstm_fasttext_embedding_meta.joblib",
        "models/deep_learning/BiLSTM_Word2Vec.keras",
        "models/deep_learning/BiLSTM_FastText.keras",
    ],
    "xlmr": ["models/transformers/xlm-roberta-base"],
    "transformers": [
        "models/transformers/mBERT_FineTuned",
        "models/transformers/SomBERTa_FineTuned",
        "models/transformers/AfroXLMR_FineTuned",
        "models/transformers/AfriBERTa_FineTuned",
    ],
}


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def load_state(restart: bool) -> dict:
    if restart or not STATE.exists():
        return {"done": [], "results": {}}
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# Model directory -> the model whose freshness decides whether it may be cleared.  A
# resume must not wipe a fine-tune that already finished against the current splits.
GUARDED = {
    "models/transformers/xlm-roberta-base": "XLMRoberta_FineTuned",
    "models/transformers/mBERT_FineTuned": "mBERT_FineTuned",
    "models/transformers/SomBERTa_FineTuned": "SomBERTa_FineTuned",
    "models/transformers/AfroXLMR_FineTuned": "AfroXLMR_FineTuned",
    "models/transformers/AfriBERTa_FineTuned": "AfriBERTa_FineTuned",
}


def clear_stale(stage: str) -> None:
    """Move a stage's Experiment 2 artifacts aside so its trainer cannot skip its work."""
    STALE_BACKUP.mkdir(parents=True, exist_ok=True)
    moved, kept = [], []
    for rel in STALE.get(stage, []):
        src = EXP_DIR / rel
        if not src.exists():
            continue
        guard = GUARDED.get(rel)
        if guard and is_current(guard):
            kept.append(rel)
            continue
        dst = STALE_BACKUP / rel.replace("/", "__")
        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        shutil.move(str(src), str(dst))
        moved.append(rel)
    if moved:
        log(f"  cleared {len(moved)} stale path(s): {', '.join(moved)}")
    if kept:
        log(f"  kept {len(kept)} already-current model(s): {', '.join(kept)}")


def stage_traditional() -> dict:
    import pandas as pd

    from experiments.run_balanced_experiments import LabelSpec, train_traditional_models

    train_df = pd.read_csv(EXP_DIR / "data" / "clean_train.csv", keep_default_na=False)
    label_names = sorted(train_df["Label"].dropna().unique().tolist())
    labels = LabelSpec(label2id={label: i for i, label in enumerate(label_names)})
    rows = train_traditional_models(EXP_DIR, SEED, labels, True, True, False)
    # NOT write_comparison(): it writes only the rows handed to it, so calling it here
    # replaced the 13-model comparison with these 4 and the dashboard silently lost the
    # neural models.  Rebuild from every report instead, after the last stage.
    return {row["model"]: row for row in rows}


def rebuild_comparison() -> dict:
    """Rewrite results/all_models_comparison.csv from every classification report.

    This file is what the web platform reads, so it has to list all 13 models -- a
    partial rebuild does not error, it just makes models disappear from the dashboard.
    """
    import numpy as np
    import pandas as pd

    data = EXP_DIR / "data"
    train = len(pd.read_csv(data / "clean_train.csv", keep_default_na=False))
    val = len(pd.read_csv(data / "clean_val.csv", keep_default_na=False))
    test = len(pd.read_csv(data / "clean_test.csv", keep_default_na=False))

    def family(model: str) -> str:
        if model.endswith("_TFIDF"):
            return "traditional_ml"
        return "deep_learning" if model.startswith("BiLSTM") else "transformers"

    rows = []
    for path in sorted((EXP_DIR / "evaluation" / "reports").glob("classification_report_*.csv")):
        model = path.stem.replace("classification_report_", "")
        report = pd.read_csv(path, index_col=0)
        fam = family(model)
        row = {
            "experiment": EXP_DIR.name,
            "family": fam,
            "model": model,
            "evaluation_train_rows": train + val,
            "test_rows": test,
            "final_train_rows": train + val + test if fam == "traditional_ml" else train + val,
            "saved_model_train_scope": "full_dataset" if fam == "traditional_ml" else "train_validation",
            "accuracy": float(report.loc["accuracy", "precision"]),
            "precision": float(report.loc["weighted avg", "precision"]),
            "recall": float(report.loc["weighted avg", "recall"]),
            "f1": float(report.loc["weighted avg", "f1-score"]),
            "macro_f1": float(report.loc["macro avg", "f1-score"]),
        }
        roc = path.parent / f"roc_curve_{model}.csv"
        if roc.exists():
            curve = pd.read_csv(roc)
            if {"fpr", "tpr"}.issubset(curve.columns):
                row["roc_auc"] = float(np.trapezoid(curve["tpr"], curve["fpr"]))
        rows.append(row)

    rows.sort(key=lambda r: (r["f1"], r["accuracy"]), reverse=True)
    out = EXP_DIR / "results" / "all_models_comparison.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    log(f"  {len(rows)} models -> {out.relative_to(ROOT)}")
    return {r["model"]: r["accuracy"] for r in rows}


def stage_keras() -> dict:
    import tensorflow as tf

    tf.get_logger().setLevel("ERROR")
    from experiments.run_full_12_steps import tokenize_with_keras, train_bilstm, train_mini_transformer

    log("  tokenizing with Keras tokenizer")
    tokenize_with_keras(EXP_DIR, max_tokens=30_000, max_length=256)
    out = {}
    log("  training BiLSTM_Keras")
    out["BiLSTM_Keras"] = train_bilstm(EXP_DIR, LABEL_NAMES, SEED)
    log("  training MiniTransformer_Keras")
    out["MiniTransformer_Keras"] = train_mini_transformer(EXP_DIR, LABEL_NAMES, SEED)
    return out


def stage_embeddings() -> dict:
    import tensorflow as tf

    tf.get_logger().setLevel("ERROR")
    from experiments.run_completion_pass import train_bilstm_with_embeddings

    out = {}
    for emb, name in [("word2vec", "BiLSTM_Word2Vec"), ("fasttext", "BiLSTM_FastText")]:
        log(f"  training {name}")
        out[name] = train_bilstm_with_embeddings(EXP_DIR, LABEL_NAMES, SEED, emb, name)
    return out


def stage_xlmr() -> dict:
    from experiments.run_full_12_steps import train_xlmr

    if is_current("XLMRoberta_FineTuned"):
        log("  XLMRoberta_FineTuned: report already newer than the splits, skipping")
        return {}
    log("  fine-tuning XLMRoberta_FineTuned")
    return {"XLMRoberta_FineTuned": train_xlmr(EXP_DIR, LABEL_NAMES, SEED, batch_size=32)}


def is_current(model_name: str) -> bool:
    """True when this model already has a report newer than the splits it must match.

    Each fine-tune costs one to two hours, so a resume has to restart at the model that
    was interrupted -- not at the top of the stage.  The splits' mtime is the reference
    because that is what makes an older report stale.
    """
    report = EXP_DIR / "evaluation" / "reports" / f"classification_report_{model_name}.csv"
    splits = EXP_DIR / "data" / "clean_train.csv"
    return report.exists() and splits.exists() and report.stat().st_mtime > splits.stat().st_mtime


def stage_transformers() -> dict:
    from experiments.run_completion_pass import TRANSFORMER_SPECS, train_hf_transformer

    out = {}
    for model_id, model_name in TRANSFORMER_SPECS:
        if is_current(model_name):
            log(f"  {model_name}: report already newer than the splits, skipping")
            continue
        log(f"  fine-tuning {model_name} ({model_id})")
        started = time.time()
        out[model_name] = train_hf_transformer(EXP_DIR, LABEL_NAMES, SEED, model_id, model_name)
        log(f"  {model_name} done in {(time.time() - started) / 60:.1f} min")
    return out


def stage_xai() -> dict:
    """SHAP, LIME and error analysis for the Experiment 2 champion.

    These are derived from the trained model and the test split, so they go stale the
    moment either changes -- and unlike a metric, a stale SHAP plot looks fine.
    """
    import pandas as pd

    from experiments.run_balanced_experiments import (
        LabelSpec,
        generate_xai_outputs,
        generate_xai_outputs_strict,
    )

    train_df = pd.read_csv(EXP_DIR / "data" / "clean_train.csv", keep_default_na=False)
    label_names = sorted(train_df["Label"].dropna().unique().tolist())
    labels = LabelSpec(label2id={label: i for i, label in enumerate(label_names)})

    log("  regenerating SHAP / LIME / error analysis for LinearSVC_TFIDF")
    generate_xai_outputs(EXP_DIR, "LinearSVC_TFIDF", labels)
    generate_xai_outputs_strict(EXP_DIR, "LinearSVC_TFIDF", labels)
    return {"xai": "LinearSVC_TFIDF"}


STAGES = [
    ("traditional", stage_traditional),
    ("keras", stage_keras),
    ("embeddings", stage_embeddings),
    ("xlmr", stage_xlmr),
    ("transformers", stage_transformers),
    ("comparison", rebuild_comparison),
    ("xai", stage_xai),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart", action="store_true", help="ignore saved progress")
    parser.add_argument("--only", action="append", dest="only", help="run only these stage(s)")
    parser.add_argument("--keep-stale", action="store_true", help="do not clear existing artifacts")
    args = parser.parse_args()

    from experiments.somali_stopwords import STOPWORD_COUNT

    log(f"Experiment 2 retrain - stop-word list: {STOPWORD_COUNT} words")

    state = load_state(args.restart)
    stages = [(n, f) for n, f in STAGES if not args.only or n in args.only]

    started_all = time.time()
    for name, fn in stages:
        if name in state["done"]:
            log(f"== {name}: already done, skipping ==")
            continue
        log(f"== {name}: starting ==")
        if not args.keep_stale:
            clear_stale(name)
        started = time.time()
        try:
            result = fn()
        except Exception:
            log(f"== {name}: FAILED ==")
            traceback.print_exc()
            save_state(state)
            return 1
        mins = (time.time() - started) / 60
        state["done"].append(name)
        state["results"][name] = {"minutes": round(mins, 1), "detail": _summarize(result)}
        save_state(state)
        log(f"== {name}: done in {mins:.1f} min ==")

    log(f"ALL STAGES COMPLETE in {(time.time() - started_all) / 60:.1f} min")
    for name, info in state["results"].items():
        log(f"  {name:14s} {info['minutes']:>6.1f} min  {info['detail']}")
    return 0


def _summarize(result: object) -> str:
    if not isinstance(result, dict):
        return str(result)[:120]
    parts = []
    for key, value in result.items():
        if isinstance(value, dict) and "accuracy" in value:
            parts.append(f"{key}={float(value['accuracy']):.4f}")
    return ", ".join(parts) if parts else str(result)[:120]


if __name__ == "__main__":
    raise SystemExit(main())
