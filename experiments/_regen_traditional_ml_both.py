"""Regenerate traditional-ML reports AND ROC curves together for both experiments.

The classification reports for the four traditional-ML models were last written by
`train_all.py`, which does not emit ROC curves, so each experiment's
`roc_curve_*.csv` for those models predates its `classification_report_*.csv`.
Re-running the canonical trainer writes both from a single fit, so the reported
accuracy/F1 and ROC-AUC describe the same model.

Safety: `train_traditional_models` calls `remove_stale_model_outputs`, which
deletes every `classification_report_*` / `confusion_matrix_*` whose model name is
not one of the four traditional-ML models. Run standalone that would destroy the
BiLSTM, MiniTransformer and fine-tuned-transformer reports. This script therefore
snapshots the evaluation directory first and restores anything the trainer removed.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from experiments.run_balanced_experiments import LabelSpec, train_traditional_models

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
EXPERIMENTS = [
    "experiment_1_stopwords_included",
    "experiment_2_stopwords_removed",
]


def snapshot(exp_dir: Path) -> Path:
    backup = exp_dir / "evaluation" / "_pre_traditional_ml_backup"
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir(parents=True)
    for sub in ("reports", "figures"):
        src = exp_dir / "evaluation" / sub
        if src.exists():
            shutil.copytree(src, backup / sub)
    return backup


def restore_missing(exp_dir: Path, backup: Path) -> list[str]:
    """Put back any file the trainer deleted that it did not rewrite."""
    restored: list[str] = []
    for sub in ("reports", "figures"):
        src_dir = backup / sub
        dst_dir = exp_dir / "evaluation" / sub
        if not src_dir.exists():
            continue
        for src in src_dir.iterdir():
            dst = dst_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
                restored.append(f"{sub}/{src.name}")
    return restored


def main() -> int:
    for name in EXPERIMENTS:
        exp_dir = ROOT / "experiments" / name
        train_df = pd.read_csv(exp_dir / "data" / "clean_train.csv", keep_default_na=False)
        label_names = sorted(train_df["Label"].astype(str).unique().tolist())
        labels = LabelSpec(label2id={label: idx for idx, label in enumerate(label_names)})

        backup = snapshot(exp_dir)
        print(f"== {name}: snapshot taken, regenerating traditional ML (labels={label_names}) ==", flush=True)
        rows = train_traditional_models(
            exp_dir,
            SEED,
            labels,
            include_xgboost=True,
            include_random_forest=True,
            tune=False,
        )
        for row in rows:
            print(f"   {row.get('model')}: acc={row.get('accuracy')} f1={row.get('f1')}", flush=True)

        restored = restore_missing(exp_dir, backup)
        print(f"== {name}: restored {len(restored)} non-traditional-ML output(s) ==", flush=True)
        for item in restored:
            print(f"   restored {item}", flush=True)
        shutil.rmtree(backup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
