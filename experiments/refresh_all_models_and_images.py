from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from experiments.run_balanced_experiments import load_table


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
EXPERIMENTS = ["experiment_1_stopwords_included", "experiment_2_stopwords_removed"]


def run(args: list[str]) -> None:
    print("\n== RUN:", " ".join(args), "==")
    subprocess.run([str(PYTHON), *args], cwd=ROOT, check=True)


def normalize_category(value: object) -> str:
    text = str(value).strip().title()
    return "Entertainment" if text == "Entertiment" else text


def normalize_ai_tool(value: object) -> str | None:
    text = re.sub(r"[^a-z]", "", str(value).lower())
    if "chatgpt" in text or "gpt" in text:
        return "ChatGPT"
    if "gemini" in text:
        return "Gemini"
    if any(token in text for token in ("claude", "cloude", "cloud", "cluade")):
        return "Claude"
    return None


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_").lower()


def generate_per_category_ai_type_images() -> None:
    raw = load_table(ROOT / "data" / "raw" / "full_dataset.xlsx").fillna("")
    raw["CategoryNorm"] = raw["Category"].map(normalize_category)
    raw["AiToolNorm"] = raw["Ai Type"].map(normalize_ai_tool)
    rows = raw[raw["CategoryNorm"].str.len().gt(0) & raw["AiToolNorm"].notna()].copy()
    pivot = rows.groupby(["CategoryNorm", "AiToolNorm"]).size().unstack(fill_value=0)
    pivot = pivot.reindex(sorted(pivot.index))
    for column in ["ChatGPT", "Claude", "Gemini"]:
        if column not in pivot.columns:
            pivot[column] = 0
    pivot = pivot[["ChatGPT", "Claude", "Gemini"]]

    for exp_name in EXPERIMENTS:
        exp_dir = ROOT / "experiments" / exp_name
        report_dir = exp_dir / "eda" / "reports"
        out_dir = exp_dir / "eda" / "figures" / "ai_type_by_category"
        report_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        pivot.to_csv(report_dir / "ai_type_by_category.csv", index_label="category")

        summary_path = report_dir / "eda_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        summary["ai_type_by_category_counts"] = {
            category: {tool: int(count) for tool, count in row.items()}
            for category, row in pivot.to_dict(orient="index").items()
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        for category in pivot.index:
            counts = pivot.loc[category].sort_values(ascending=False)
            plt.figure(figsize=(6, 4))
            ax = sns.barplot(x=counts.index, y=counts.values, hue=counts.index, palette="Set2", legend=False)
            for container in ax.containers:
                ax.bar_label(container, fmt="%d", padding=3, fontsize=9)
            plt.title(f"{category}: AI type distribution")
            plt.xlabel("AI Type")
            plt.ylabel("Rows")
            plt.tight_layout()
            plt.savefig(out_dir / f"{safe_filename(category)}_ai_type_distribution.svg", dpi=180)
            plt.close()


def main() -> int:
    run(["experiments/run_full_12_steps.py", "--skip-xlm-r"])
    run(["train_all.py", "--force-all", "--skip-traditional", "--skip-deep", "--skip-outputs"])
    run(["experiments/run_completion_pass.py", "--skip-transformers", "--skip-embeddings", "--skip-tuning", "--skip-xai"])
    run(["experiments/build_balanced_refresh_report.py"])
    run(["experiments/regenerate_eda_images.py"])
    generate_per_category_ai_type_images()
    print("\nFull refresh complete: models, metrics, reports, EDA images, and per-category AI-type images.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
