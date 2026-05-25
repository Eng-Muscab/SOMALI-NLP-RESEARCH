"""
STEP 8 trainer:
- Fine-tune mBERT, XLM-R, SomBERTa, AfroXLMR, AfriBERTa
- Save best checkpoint per model
- Save training logs per model
- Generate comparison table
"""

from __future__ import annotations

import argparse
import inspect
import random
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yaml
from datasets import Dataset
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    set_seed,
)


MODEL_ORDER = ["mbert", "xlmr", "somberta", "afroxlmr", "afriberta"]


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


def maybe_limit(df: pd.DataFrame, n: int | None, seed: int) -> pd.DataFrame:
    if n is None or n <= 0 or n >= len(df):
        return df.reset_index(drop=True)
    return df.sample(n=n, random_state=seed).reset_index(drop=True)


def prepare_split(
    split_path: Path,
    text_col: str,
    label_col: str,
    max_samples: int | None,
    seed: int,
) -> pd.DataFrame:
    df = pd.read_csv(split_path)
    required = [text_col, label_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{split_path.name} missing columns: {missing}")

    out = df[[text_col, label_col]].dropna().copy()
    out[label_col] = encode_labels(out[label_col])
    out = out.rename(columns={text_col: "text", label_col: "labels"})
    out = maybe_limit(out, max_samples, seed)
    return out


def prepare_datasets(
    project_root: Path,
    cfg: Dict,
    max_train_samples: int | None,
    max_val_samples: int | None,
    max_test_samples: int | None,
) -> Tuple[Dataset, Dataset, Dataset]:
    seed = int(cfg["project"]["seed"])
    processed_dir = resolve_path(project_root, cfg["paths"]["data_processed_dir"])
    text_col = cfg["data"]["text_column"]
    label_col = cfg["data"]["label_column"]

    train_df = prepare_split(
        split_path=processed_dir / cfg["data"]["train_file"],
        text_col=text_col,
        label_col=label_col,
        max_samples=max_train_samples,
        seed=seed,
    )
    val_df = prepare_split(
        split_path=processed_dir / cfg["data"]["val_file"],
        text_col=text_col,
        label_col=label_col,
        max_samples=max_val_samples,
        seed=seed,
    )
    test_df = prepare_split(
        split_path=processed_dir / cfg["data"]["test_file"],
        text_col=text_col,
        label_col=label_col,
        max_samples=max_test_samples,
        seed=seed,
    )

    train_ds = Dataset.from_pandas(train_df, preserve_index=False)
    val_ds = Dataset.from_pandas(val_df, preserve_index=False)
    test_ds = Dataset.from_pandas(test_df, preserve_index=False)
    return train_ds, val_ds, test_ds


def compute_metrics(eval_pred) -> Dict[str, float]:
    logits, labels = eval_pred
    if isinstance(logits, tuple):
        logits = logits[0]
    preds = np.argmax(logits, axis=-1)
    acc = accuracy_score(labels, preds)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, preds, average="binary", zero_division=0
    )
    return {
        "accuracy": float(acc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def tokenize_dataset(ds: Dataset, tokenizer: AutoTokenizer, max_len: int) -> Dataset:
    def _tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=max_len)

    return ds.map(_tokenize, batched=True, remove_columns=["text"])


def build_training_args(output_dir: Path, cfg_tf: Dict, seed: int) -> TrainingArguments:
    params = inspect.signature(TrainingArguments.__init__).parameters
    kwargs: Dict[str, object] = {}

    # Always required in every known Transformers version.
    kwargs["output_dir"] = output_dir.as_posix()

    candidate_kwargs = {
        "overwrite_output_dir": True,
        "learning_rate": float(cfg_tf["learning_rate"]),
        "weight_decay": float(cfg_tf["weight_decay"]),
        "num_train_epochs": float(cfg_tf["epochs"]),
        "per_device_train_batch_size": int(cfg_tf["batch_size"]),
        "per_device_eval_batch_size": int(cfg_tf["eval_batch_size"]),
        "gradient_accumulation_steps": int(cfg_tf["gradient_accumulation_steps"]),
        "warmup_ratio": float(cfg_tf["warmup_ratio"]),
        "save_strategy": "epoch",
        "logging_strategy": "steps",
        "logging_steps": int(cfg_tf["logging_steps"]),
        "save_total_limit": int(cfg_tf["save_total_limit"]),
        "load_best_model_at_end": True,
        "metric_for_best_model": str(cfg_tf["metric_for_best_model"]),
        "greater_is_better": bool(cfg_tf["greater_is_better"]),
        "report_to": "none",
        "seed": seed,
        "data_seed": seed,
        "fp16": bool(cfg_tf["fp16"]),
    }

    # Filter unknown kwargs to stay compatible with both old/new Transformers APIs.
    for key, value in candidate_kwargs.items():
        if key in params:
            kwargs[key] = value

    if "eval_strategy" in params:
        kwargs["eval_strategy"] = "epoch"
    elif "evaluation_strategy" in params:
        kwargs["evaluation_strategy"] = "epoch"

    return TrainingArguments(**kwargs)


def save_training_log(trainer: Trainer, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    history = trainer.state.log_history
    if history:
        pd.DataFrame(history).to_csv(out_path, index=False)
    else:
        pd.DataFrame([{"note": "No log history found."}]).to_csv(out_path, index=False)


def copy_best_checkpoint(best_src: str | None, best_dst: Path) -> str:
    if best_src is None:
        return ""
    src = Path(best_src)
    if not src.exists():
        return ""
    if best_dst.exists():
        shutil.rmtree(best_dst)
    shutil.copytree(src, best_dst)
    return best_dst.as_posix()


def default_transformer_cfg() -> Dict:
    return {
        "models": {
            "mbert": "bert-base-multilingual-cased",
            "xlmr": "xlm-roberta-base",
            "somberta": "shuabdaud/SomBERTa",
            "afroxlmr": "Davlan/afro-xlmr-base",
            "afriberta": "castorini/afriberta_base",
        },
        "num_labels": 2,
        "batch_size": 8,
        "eval_batch_size": 16,
        "learning_rate": 2e-5,
        "weight_decay": 0.01,
        "epochs": 3,
        "warmup_ratio": 0.1,
        "gradient_accumulation_steps": 1,
        "early_stopping_patience": 2,
        "save_total_limit": 2,
        "logging_steps": 25,
        "metric_for_best_model": "f1",
        "greater_is_better": True,
        "fp16": False,
    }


def merge_cfg(user_cfg: Dict, default_cfg: Dict) -> Dict:
    out = dict(default_cfg)
    for k, v in user_cfg.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            merged = dict(out[k])
            merged.update(v)
            out[k] = merged
        else:
            out[k] = v
    return out


def train_one_model(
    model_key: str,
    model_id: str,
    train_ds: Dataset,
    val_ds: Dataset,
    test_ds: Dataset,
    cfg_tf: Dict,
    max_len: int,
    logs_dir: Path,
    checkpoints_dir: Path,
    seed: int,
    trust_remote_code: bool,
) -> Dict[str, object]:
    model_root = checkpoints_dir / model_key
    run_dir = model_root / "run"
    best_dir = model_root / "best"
    log_file = logs_dir / f"{model_key}_training_log.csv"
    model_root.mkdir(parents=True, exist_ok=True)

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            use_fast=True,
            trust_remote_code=trust_remote_code,
        )
        if tokenizer.pad_token is None:
            fallback_pad = tokenizer.eos_token or tokenizer.unk_token
            if fallback_pad is not None:
                tokenizer.pad_token = fallback_pad

        model = AutoModelForSequenceClassification.from_pretrained(
            model_id,
            num_labels=int(cfg_tf["num_labels"]),
            trust_remote_code=trust_remote_code,
        )
        if model.config.pad_token_id is None and tokenizer.pad_token_id is not None:
            model.config.pad_token_id = tokenizer.pad_token_id
    except Exception as exc:
        return {
            "Model Name": model_key,
            "HF Model ID": model_id,
            "Accuracy": "",
            "Precision": "",
            "Recall": "",
            "F1-Score": "",
            "Val Accuracy": "",
            "Best Checkpoint": "",
            "Status": f"failed_to_load: {exc}",
        }

    tok_train = tokenize_dataset(train_ds, tokenizer, max_len=max_len)
    tok_val = tokenize_dataset(val_ds, tokenizer, max_len=max_len)
    tok_test = tokenize_dataset(test_ds, tokenizer, max_len=max_len)
    collator = DataCollatorWithPadding(tokenizer=tokenizer)

    args = build_training_args(run_dir, cfg_tf, seed=seed)
    callbacks = []
    patience = int(cfg_tf["early_stopping_patience"])
    if patience > 0:
        callbacks.append(EarlyStoppingCallback(early_stopping_patience=patience))

    trainer_kwargs = {
        "model": model,
        "args": args,
        "train_dataset": tok_train,
        "eval_dataset": tok_val,
        "tokenizer": tokenizer,
        "data_collator": collator,
        "compute_metrics": compute_metrics,
        "callbacks": callbacks,
    }
    trainer_params = inspect.signature(Trainer.__init__).parameters
    filtered_trainer_kwargs = {
        k: v for k, v in trainer_kwargs.items() if k in trainer_params
    }
    trainer = Trainer(**filtered_trainer_kwargs)

    try:
        trainer.train()
        save_training_log(trainer, log_file)
        trainer.save_state()

        best_ckpt = copy_best_checkpoint(trainer.state.best_model_checkpoint, best_dir)
        if not best_ckpt:
            trainer.save_model(best_dir.as_posix())
            tokenizer.save_pretrained(best_dir.as_posix())
            best_ckpt = best_dir.as_posix()
        else:
            tokenizer.save_pretrained(best_dir.as_posix())

        val_metrics = trainer.evaluate(eval_dataset=tok_val)
        pred = trainer.predict(tok_test)
        pred_labels = np.argmax(pred.predictions, axis=-1)
        gold_labels = np.array(tok_test["labels"])

        acc = accuracy_score(gold_labels, pred_labels)
        precision, recall, f1, _ = precision_recall_fscore_support(
            gold_labels, pred_labels, average="binary", zero_division=0
        )
        val_acc = float(val_metrics.get("eval_accuracy", np.nan))

        return {
            "Model Name": model_key,
            "HF Model ID": model_id,
            "Accuracy": f"{acc * 100:.2f}%",
            "Precision": float(precision),
            "Recall": float(recall),
            "F1-Score": float(f1),
            "Val Accuracy": f"{val_acc * 100:.2f}%" if not np.isnan(val_acc) else "",
            "Best Checkpoint": best_ckpt,
            "Status": "ok",
        }
    except Exception as exc:
        return {
            "Model Name": model_key,
            "HF Model ID": model_id,
            "Accuracy": "",
            "Precision": "",
            "Recall": "",
            "F1-Score": "",
            "Val Accuracy": "",
            "Best Checkpoint": "",
            "Status": f"failed_to_train: {exc}",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="STEP 8 Transformer fine-tuning")
    parser.add_argument("--config", default="config.yaml", help="Path to config yaml")
    parser.add_argument(
        "--model",
        choices=["all", *MODEL_ORDER],
        default="all",
        help="Which model to fine-tune",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick run for testing (small sample + 1 epoch)",
    )
    parser.add_argument("--max-train-samples", type=int, default=None)
    parser.add_argument("--max-val-samples", type=int, default=None)
    parser.add_argument("--max-test-samples", type=int, default=None)
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="Enable trust_remote_code for custom model repos",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = find_project_root(Path.cwd())
    config_path = resolve_path(project_root, args.config)
    cfg = load_config(config_path)

    seed = int(cfg["project"]["seed"])
    random.seed(seed)
    np.random.seed(seed)
    set_seed(seed)

    cfg_tf = merge_cfg(cfg.get("transformers", {}), default_transformer_cfg())
    if args.quick:
        cfg_tf["epochs"] = 1
        if args.max_train_samples is None:
            args.max_train_samples = 1000
        if args.max_val_samples is None:
            args.max_val_samples = 300
        if args.max_test_samples is None:
            args.max_test_samples = 300

    max_len = int(cfg.get("tokenization", {}).get("max_length", 256))

    logs_dir = resolve_path(project_root, cfg["paths"]["transformer_logs_dir"])
    checkpoints_dir = resolve_path(project_root, cfg["paths"]["transformer_checkpoints_dir"])
    logs_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    train_ds, val_ds, test_ds = prepare_datasets(
        project_root=project_root,
        cfg=cfg,
        max_train_samples=args.max_train_samples,
        max_val_samples=args.max_val_samples,
        max_test_samples=args.max_test_samples,
    )

    model_map = cfg_tf["models"]
    model_keys = MODEL_ORDER if args.model == "all" else [args.model]

    rows: List[Dict[str, object]] = []
    for model_key in model_keys:
        model_id = model_map.get(model_key)
        if not model_id:
            rows.append(
                {
                    "Model Name": model_key,
                    "HF Model ID": "",
                    "Accuracy": "",
                    "Precision": "",
                    "Recall": "",
                    "F1-Score": "",
                    "Val Accuracy": "",
                    "Best Checkpoint": "",
                    "Status": "missing_model_id_in_config",
                }
            )
            continue

        print(f"\n=== Fine-tuning {model_key}: {model_id} ===")
        row = train_one_model(
            model_key=model_key,
            model_id=model_id,
            train_ds=train_ds,
            val_ds=val_ds,
            test_ds=test_ds,
            cfg_tf=cfg_tf,
            max_len=max_len,
            logs_dir=logs_dir,
            checkpoints_dir=checkpoints_dir,
            seed=seed,
            trust_remote_code=args.trust_remote_code,
        )
        rows.append(row)
        print(row)

    out_df = pd.DataFrame(rows)
    local_csv = project_root / "models" / "transformers" / "model_comparison_metrics.csv"
    out_df.to_csv(local_csv, index=False)
    print(f"\nSaved comparison table: {local_csv}")

    results_csv = project_root / "results" / "transformers_model_comparison.csv"
    results_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(results_csv, index=False)
    print(f"Updated results table: {results_csv}")


if __name__ == "__main__":
    main()
