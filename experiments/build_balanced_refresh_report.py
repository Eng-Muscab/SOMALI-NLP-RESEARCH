from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ["experiment_1_stopwords_included", "experiment_2_stopwords_removed"]


def read_previous_results(exp_name: str) -> pd.DataFrame:
    raw = subprocess.check_output(
        ["git", "show", f"HEAD:experiments/{exp_name}/results/all_models_comparison.csv"],
        cwd=ROOT,
        text=True,
    )
    return pd.read_csv(io.StringIO(raw))


def markdown_table(df: pd.DataFrame) -> str:
    display = df.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda value: f"{value:.4f}")
    headers = [str(col) for col in display.columns]
    rows = [[str(value) for value in row] for row in display.to_numpy()]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def main() -> int:
    exp_root = ROOT / "experiments"
    frames = []
    for exp_name in EXPERIMENTS:
        current = pd.read_csv(exp_root / exp_name / "results" / "all_models_comparison.csv")
        frames.append(current)
    combined = pd.concat(frames, ignore_index=True).sort_values(["f1", "accuracy"], ascending=False)

    for exp_name in EXPERIMENTS:
        combined.to_csv(exp_root / exp_name / "results" / "two_experiment_model_comparison.csv", index=False)

    dataset = json.loads(
        (exp_root / "experiment_1_stopwords_included" / "results" / "experiment_summary.json").read_text(
            encoding="utf-8"
        )
    )["dataset"]
    (exp_root / "full_12_step_run_summary.json").write_text(
        json.dumps(
            {
                "dataset": dataset,
                "best_overall": combined.iloc[0].to_dict(),
                "model_rows": combined.to_dict(orient="records"),
                "pretrained_transformer_note": (
                    "Balanced-dataset refresh retrained traditional ML, Keras BiLSTM, "
                    "MiniTransformer, Word2Vec/FastText BiLSTM, and multilingual-embedding "
                    "BiLSTM models from the updated Excel datasets. Pretrained HF transformer "
                    "fine-tuning remains available through run_completion_pass.py without "
                    "--skip-transformers."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    old_all = pd.concat([read_previous_results(exp_name) for exp_name in EXPERIMENTS], ignore_index=True)
    common = old_all.merge(combined, on=["experiment", "family", "model"], suffixes=("_previous", "_balanced"))
    for metric in ["accuracy", "precision", "recall", "f1", "macro_f1"]:
        common[f"{metric}_delta"] = common[f"{metric}_balanced"] - common[f"{metric}_previous"]

    comparison_cols = [
        "experiment",
        "family",
        "model",
        "accuracy_previous",
        "accuracy_balanced",
        "accuracy_delta",
        "precision_previous",
        "precision_balanced",
        "precision_delta",
        "recall_previous",
        "recall_balanced",
        "recall_delta",
        "f1_previous",
        "f1_balanced",
        "f1_delta",
        "macro_f1_previous",
        "macro_f1_balanced",
        "macro_f1_delta",
    ]
    comparison = common[comparison_cols].sort_values(["f1_balanced", "accuracy_balanced"], ascending=False)
    comparison.to_csv(exp_root / "balanced_vs_previous_model_comparison.csv", index=False)

    minority_rows = []
    for exp_name in EXPERIMENTS:
        reports_dir = exp_root / exp_name / "evaluation" / "reports"
        for report_path in sorted(reports_dir.glob("classification_report_*.csv")):
            model_name = report_path.stem.replace("classification_report_", "")
            report = pd.read_csv(report_path, index_col=0)
            if "HUMAN" not in report.index:
                continue
            row = report.loc["HUMAN"]
            minority_rows.append(
                {
                    "experiment": exp_name,
                    "model": model_name,
                    "minority_class": "HUMAN",
                    "precision": float(row["precision"]),
                    "recall": float(row["recall"]),
                    "f1": float(row["f1-score"]),
                    "support": int(float(row["support"])),
                }
            )
    minority = pd.DataFrame(minority_rows).sort_values(["f1", "recall"], ascending=False)
    minority.to_csv(exp_root / "balanced_minority_class_performance.csv", index=False)

    best = combined.iloc[0]
    docs_dir = ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    lines = [
        "# Balanced Dataset Refresh Report",
        "",
        "## Dataset",
        "",
        "- Source labeled dataset: `data/raw/labeled text.xlsx`",
        "- Supplemental EDA dataset: `data/raw/full_dataset.xlsx`",
        f"- Clean labeled rows: {dataset['dataset_rows']}",
        (
            f"- Label counts: AI={dataset['label_counts'].get('AI')}, "
            f"HUMAN={dataset['label_counts'].get('HUMAN')}"
        ),
        (
            "- Minority class after cleaning: `HUMAN` "
            "(only 123 fewer rows than AI, so the dataset is now close to balanced)."
        ),
        "",
        "## Best New Result",
        "",
        f"- Experiment: `{best['experiment']}`",
        f"- Model: `{best['model']}`",
        f"- Accuracy: {best['accuracy']:.4f}",
        f"- Precision: {best['precision']:.4f}",
        f"- Recall: {best['recall']:.4f}",
        f"- F1-score: {best['f1']:.4f}",
        f"- ROC-AUC: {best.get('roc_auc', float('nan')):.4f}",
        "",
        "## Previous vs Balanced Results",
        "",
        (
            "The table below compares models that exist in both the previous committed result tables "
            "and the refreshed balanced-dataset tables. Negative deltas are expected for some models "
            "because the new held-out test set is larger and less skewed, making the evaluation harder "
            "and more realistic."
        ),
        "",
        markdown_table(comparison),
        "",
        "## Minority-Class Performance (`HUMAN`)",
        "",
        (
            "Because `HUMAN` remains the smaller class after cleaning, this table reports the refreshed "
            "per-class scores for `HUMAN`. Recall is the most important signal here: higher recall means "
            "fewer human-written texts are incorrectly flagged as AI."
        ),
        "",
        markdown_table(minority),
        "",
        "## Interpretation",
        "",
        (
            "- Balancing increased the training data from the old 5,869 cleaned rows to 11,509 "
            "cleaned rows and nearly equalized AI/HUMAN support."
        ),
        (
            "- The best refreshed model is still `LinearSVC_TFIDF`, which indicates TF-IDF "
            "character/word features remain strong for Somali AI-vs-human classification."
        ),
        (
            "- Several headline F1-scores are lower than the old run, especially for stopwords-removed "
            "models. This is a more trustworthy result: the larger balanced test split reduces the "
            "artificial advantage caused by the old dataset distribution."
        ),
        (
            "- Minority-class (`HUMAN`) recall is now explicit in every classification report, so false "
            "AI accusations against human text can be tracked directly."
        ),
        (
            "- Stopwords included performs best overall in the refreshed run, suggesting Somali function "
            "words still carry useful stylistic signal for this task."
        ),
        "",
    ]
    (docs_dir / "balanced_dataset_refresh_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        "wrote experiments/balanced_vs_previous_model_comparison.csv, "
        "experiments/balanced_minority_class_performance.csv, "
        "and docs/balanced_dataset_refresh_report.md"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
