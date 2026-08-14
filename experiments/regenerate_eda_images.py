from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if ROOT.as_posix() not in sys.path:
    sys.path.insert(0, ROOT.as_posix())

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from experiments.run_balanced_experiments import load_table, normalize_category
from experiments.run_full_12_steps import generate_eda


EXPERIMENTS = ["experiment_1_stopwords_included", "experiment_2_stopwords_removed"]



def normalize_ai_tool(value: object) -> str | None:
    text = re.sub(r"[^a-z]", "", str(value).lower())
    if "chatgpt" in text or "gpt" in text:
        return "ChatGPT"
    if "gemini" in text:
        return "Gemini"
    if any(token in text for token in ("claude", "cloude", "cloud", "cluade")):
        return "Claude"
    return None


def barplot(path: Path, title: str, counts: pd.Series, color: str) -> None:
    plt.figure(figsize=(10, 5))
    ax = sns.barplot(x=counts.index, y=counts.values, color=color)
    for container in ax.containers:
        ax.bar_label(container, fmt="%d", padding=3, fontsize=8)
    plt.title(title)
    plt.xlabel("Category")
    plt.ylabel("Rows")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def main() -> int:
    raw_path = ROOT / "data" / "raw" / "full_dataset.xlsx"
    raw = load_table(raw_path).fillna("")
    raw["CategoryNorm"] = raw["Category"].map(normalize_category)
    raw["AiToolNorm"] = raw["Ai Type"].map(normalize_ai_tool)

    category_rows = raw[raw["CategoryNorm"].ne("Unknown")].copy()
    ai_rows = category_rows[category_rows["AiToolNorm"].notna()].copy()
    category_counts = category_rows["CategoryNorm"].value_counts()
    ai_category_counts = ai_rows["CategoryNorm"].value_counts().reindex(category_counts.index, fill_value=0)
    ai_tool_counts = raw["AiToolNorm"].dropna().value_counts()
    pivot = ai_rows.groupby(["CategoryNorm", "AiToolNorm"]).size().unstack(fill_value=0).reindex(category_counts.index, fill_value=0)

    summary_extra = {
        "category_counts": {k: int(v) for k, v in category_counts.to_dict().items()},
        "ai_generated_category_counts": {k: int(v) for k, v in ai_category_counts.to_dict().items()},
        "category_counts_normalized": {k: int(v) for k, v in category_counts.to_dict().items()},
        "ai_generated_category_counts_normalized": {k: int(v) for k, v in ai_category_counts.to_dict().items()},
        "ai_type_counts": {k: int(v) for k, v in ai_tool_counts.to_dict().items()},
    }

    for exp_name in EXPERIMENTS:
        exp_dir = ROOT / "experiments" / exp_name
        generate_eda(exp_dir)

        fig_dir = exp_dir / "eda" / "figures"
        report_dir = exp_dir / "eda" / "reports"
        fig_dir.mkdir(parents=True, exist_ok=True)
        report_dir.mkdir(parents=True, exist_ok=True)

        barplot(fig_dir / "category_distribution.svg", "Category distribution", category_counts, "#4c72b0")
        barplot(
            fig_dir / "ai_generated_category_distribution.svg",
            "AI-generated articles by category",
            ai_category_counts,
            "#55a868",
        )
        barplot(fig_dir / "ai_category_distribution.svg", "AI-generated articles by category", ai_category_counts, "#55a868")

        plt.figure(figsize=(6, 6))
        plt.pie(ai_tool_counts.values, labels=ai_tool_counts.index, autopct="%1.1f%%", startangle=90)
        plt.title("AI type distribution")
        plt.tight_layout()
        plt.savefig(fig_dir / "ai_type_distribution.svg", dpi=180)
        plt.close()

        ax = pivot.plot(kind="bar", stacked=True, figsize=(11, 5))
        totals = pivot.sum(axis=1)
        for idx, total in enumerate(totals):
            ax.text(idx, total + totals.max() * 0.015, str(int(total)), ha="center", va="bottom", fontsize=8)
        ax.set_ylim(0, totals.max() * 1.14)
        plt.title("AI type by category")
        plt.xlabel("Category")
        plt.ylabel("Rows")
        plt.xticks(rotation=45, ha="right")
        plt.legend(title="AI Type")
        plt.tight_layout()
        plt.savefig(fig_dir / "ai_type_by_category.svg", dpi=180)
        plt.close()

        summary_path = report_dir / "eda_summary.json"
        payload = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        payload.update(summary_extra)
        summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Regenerated EDA images from data/raw/full_dataset.xlsx and current experiment splits.")
    print(json.dumps(summary_extra, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
