"""Train traditional ML models from existing experiment splits (no xlsx required)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = next(
    (path for path in [Path(__file__).resolve(), *Path(__file__).resolve().parents] if (path / "config.yaml").exists()),
    None,
)
if PROJECT_ROOT is not None and PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

from experiments.run_balanced_experiments import (  # noqa: E402
    LabelSpec,
    find_project_root,
    train_traditional_models,
)


DEFAULT_EXPERIMENTS = [
    "experiment_1_stopwords_included",
    "experiment_2_stopwords_removed",
]


def write_comparison(exp_dir: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    results_dir = exp_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    comparison = pd.DataFrame(rows).sort_values(["f1", "accuracy"], ascending=False)
    comparison.to_csv(results_dir / "all_models_comparison.csv", index=False)
    best = comparison.iloc[0]
    (results_dir / "best_model_summary.md").write_text(
        "# Best Model Summary\n\n"
        f"- experiment: {best['experiment']}\n"
        f"- family: {best['family']}\n"
        f"- model: {best['model']}\n"
        f"- accuracy: {best['accuracy']:.4f}\n"
        f"- precision: {best['precision']:.4f}\n"
        f"- recall: {best['recall']:.4f}\n"
        f"- f1: {best['f1']:.4f}\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train traditional ML models using existing clean_train/val/test splits.",
    )
    parser.add_argument(
        "--experiment",
        action="append",
        dest="experiments",
        help="Experiment folder name under experiments/ (repeatable). Defaults to both experiments.",
    )
    parser.add_argument(
        "--include-xgboost",
        action="store_true",
        help="Also train XGBoost_TFIDF.",
    )
    parser.add_argument(
        "--include-random-forest",
        action="store_true",
        help="Also train RandomForest_TFIDF.",
    )
    parser.add_argument(
        "--all-traditional",
        action="store_true",
        help="Train all four traditional ML models (LogisticRegression, LinearSVC, RandomForest, XGBoost).",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run GridSearchCV instead of fixed defaults.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    include_rf = args.include_random_forest or args.all_traditional
    include_xgb = args.include_xgboost or args.all_traditional
    root = find_project_root(Path(__file__).resolve().parent)
    exp_names = args.experiments or DEFAULT_EXPERIMENTS

    summary: dict[str, object] = {"experiments": {}, "trained_models": 0}
    for name in exp_names:
        exp_dir = root / "experiments" / name
        train_path = exp_dir / "data" / "clean_train.csv"
        if not train_path.exists():
            print(f"Skipping {name}: missing {train_path}")
            summary["experiments"][name] = {"status": "skipped", "reason": "missing splits"}
            continue

        train_df = pd.read_csv(train_path, keep_default_na=False)
        label_names = sorted(train_df["Label"].dropna().unique().tolist())
        if len(label_names) < 2:
            print(f"Skipping {name}: need at least two label classes")
            summary["experiments"][name] = {"status": "skipped", "reason": "insufficient labels"}
            continue

        labels = LabelSpec(label2id={label: idx for idx, label in enumerate(label_names)})
        print(f"Training traditional ML models for {name}...")
        rows = train_traditional_models(
            exp_dir,
            args.seed,
            labels,
            include_xgb,
            include_rf,
            args.tune,
        )
        write_comparison(exp_dir, rows)
        summary["experiments"][name] = {
            "status": "ok",
            "models": [row["model"] for row in rows],
            "rows": len(rows),
        }
        summary["trained_models"] = int(summary["trained_models"]) + len(rows)
        print(f"Saved {len(rows)} models under {exp_dir / 'models' / 'traditional_ml'}")

    out_path = root / "experiments" / "train_from_splits_summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Summary:", out_path)
    return 0 if summary["trained_models"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
