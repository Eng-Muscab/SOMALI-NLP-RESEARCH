from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


SOMALI_FUNCTION_WORDS = {
    "aa",
    "ah",
    "ay",
    "ayaa",
    "baan",
    "buu",
    "iyo",
    "in",
    "is",
    "ka",
    "ku",
    "la",
    "looga",
    "loo",
    "marka",
    "oo",
    "si",
    "u",
    "waa",
    "waxaa",
    "waxay",
    "waxa",
    "wuxuu",
}


@dataclass(frozen=True)
class LabelSpec:
    label2id: dict[str, int]

    @property
    def id2label(self) -> dict[int, str]:
        return {v: k for k, v in self.label2id.items()}


def find_project_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "config.yaml").exists():
            return path
    raise FileNotFoundError("config.yaml not found")


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def normalize_labels(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def remove_function_words(text: str) -> str:
    tokens = re.findall(r"\b\w+\b", str(text).lower())
    return " ".join(token for token in tokens if token not in SOMALI_FUNCTION_WORDS)


def build_models(seed: int) -> dict[str, Pipeline]:
    return {
        "LogisticRegression_TFIDF": Pipeline(
            [
                ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
                ("clf", LogisticRegression(max_iter=2000)),
            ]
        ),
        "LinearSVC_TFIDF": Pipeline(
            [
                ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
                ("clf", LinearSVC()),
            ]
        ),
        "RandomForest_TFIDF": Pipeline(
            [
                ("tfidf", TfidfVectorizer(max_features=20000, ngram_range=(1, 2))),
                ("clf", RandomForestClassifier(n_estimators=300, random_state=seed)),
            ]
        ),
    }


def metric_row(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    accuracy = accuracy_score(y_true, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def save_confusion_matrix(path: Path, y_true: np.ndarray, y_pred: np.ndarray, labels: list[str], title: str) -> None:
    cm = confusion_matrix(y_true, y_pred)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=labels, yticklabels=labels)
    plt.title(title)
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def run_experiment(
    experiment_name: str,
    description: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    text_col: str,
    label_col: str,
    labels: LabelSpec,
    seed: int,
    out_root: Path,
) -> list[dict[str, object]]:
    exp_dir = out_root / experiment_name
    reports_dir = exp_dir / "reports"
    figures_dir = exp_dir / "figures"
    data_dir = exp_dir / "data"
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    train_df.to_csv(data_dir / "clean_train.csv", index=False)
    test_df.to_csv(data_dir / "clean_test.csv", index=False)

    y_train = train_df[label_col].map(labels.label2id).to_numpy(dtype=int)
    y_test = test_df[label_col].map(labels.label2id).to_numpy(dtype=int)
    x_train = train_df[text_col].astype(str).tolist()
    x_test = test_df[text_col].astype(str).tolist()

    rows: list[dict[str, object]] = []
    for model_name, pipe in build_models(seed).items():
        print(f"== {experiment_name}: training {model_name} ==")
        pipe.fit(x_train, y_train)
        y_pred = pipe.predict(x_test)
        row = {
            "experiment": experiment_name,
            "description": description,
            "model": model_name,
            **metric_row(y_test, y_pred),
        }
        rows.append(row)

        report_text = classification_report(
            y_test,
            y_pred,
            target_names=[labels.id2label[0], labels.id2label[1]],
            zero_division=0,
        )
        (reports_dir / f"classification_report_{model_name}.txt").write_text(report_text, encoding="utf-8")

        report_dict = classification_report(
            y_test,
            y_pred,
            target_names=[labels.id2label[0], labels.id2label[1]],
            output_dict=True,
            zero_division=0,
        )
        pd.DataFrame(report_dict).transpose().to_csv(
            reports_dir / f"classification_report_{model_name}.csv",
            index_label="label",
        )

        save_confusion_matrix(
            figures_dir / f"confusion_matrix_{model_name}.png",
            y_test,
            y_pred,
            labels=[labels.id2label[0], labels.id2label[1]],
            title=f"{experiment_name}: {model_name}",
        )

    pd.DataFrame(rows).sort_values(["accuracy", "f1"], ascending=False).to_csv(
        reports_dir / "metrics.csv",
        index=False,
    )
    (reports_dir / "summary.json").write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")
    (exp_dir / "README.md").write_text(
        f"# {experiment_name}\n\n"
        f"{description}\n\n"
        "Outputs:\n"
        "- `data/`: train and test files used for this experiment.\n"
        "- `reports/metrics.csv`: model-level accuracy, precision, recall, and F1-score.\n"
        "- `reports/classification_report_*.csv`: per-class metrics.\n"
        "- `figures/confusion_matrix_*.png`: confusion matrix images.\n",
        encoding="utf-8",
    )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run stop-word ablation experiments.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--out-dir", default="experiments")
    args = parser.parse_args()

    root = find_project_root(Path.cwd())
    cfg = load_config(resolve_path(root, args.config))
    processed_dir = resolve_path(root, cfg["paths"]["data_processed_dir"])
    text_col = cfg["data"]["text_column"]
    label_col = cfg["data"]["label_column"]
    seed = int(cfg["project"]["seed"])

    train_base = pd.read_csv(processed_dir / cfg["data"]["train_file"])
    test_base = pd.read_csv(processed_dir / cfg["data"]["test_file"])
    for df in (train_base, test_base):
        df[text_col] = df[text_col].astype(str)
        df[label_col] = normalize_labels(df[label_col])

    labels = LabelSpec(label2id={"HUMAN": 0, "AI": 1})
    out_root = root / args.out_dir
    out_root.mkdir(parents=True, exist_ok=True)

    included_train = train_base.copy()
    included_test = test_base.copy()
    removed_train = train_base.copy()
    removed_test = test_base.copy()
    removed_train[text_col] = removed_train[text_col].map(remove_function_words)
    removed_test[text_col] = removed_test[text_col].map(remove_function_words)

    all_rows: list[dict[str, object]] = []
    all_rows.extend(
        run_experiment(
            "experiment_1_stopwords_included",
            "Function words are kept in the text, including words such as aa, is, ku, in, iyo, ka, la, u, oo, ay.",
            included_train,
            included_test,
            text_col,
            label_col,
            labels,
            seed,
            out_root,
        )
    )
    all_rows.extend(
        run_experiment(
            "experiment_2_stopwords_removed",
            "Function words are removed before training and testing to measure how much they affect model performance.",
            removed_train,
            removed_test,
            text_col,
            label_col,
            labels,
            seed,
            out_root,
        )
    )

    comparison = pd.DataFrame(all_rows).sort_values(["model", "experiment"])
    comparison.to_csv(out_root / "stopword_ablation_comparison.csv", index=False)
    (out_root / "README.md").write_text(
        "# Stopword Ablation Experiments\n\n"
        "This folder separates the two experiments requested for function-word analysis.\n\n"
        "- `experiment_1_stopwords_included/`: Somali function words are kept.\n"
        "- `experiment_2_stopwords_removed/`: Somali function words are removed.\n"
        "- `stopword_ablation_comparison.csv`: combined comparison table for both experiments.\n",
        encoding="utf-8",
    )

    print("Saved:", out_root / "stopword_ablation_comparison.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
