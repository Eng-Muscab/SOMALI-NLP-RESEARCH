from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def find_project_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "config.yaml").exists():
            return path
    raise FileNotFoundError("config.yaml not found")


def main() -> int:
    root = find_project_root(Path.cwd())
    experiments_dir = root / "experiments"
    comparison_path = experiments_dir / "stopword_ablation_comparison.csv"
    out_path = experiments_dir / "stopword_ablation_f1_comparison.png"

    df = pd.read_csv(comparison_path)
    df["experiment_label"] = df["experiment"].map(
        {
            "experiment_1_stopwords_included": "Stopwords included",
            "experiment_2_stopwords_removed": "Stopwords removed",
        }
    )
    pivot = df.pivot(index="model", columns="experiment_label", values="f1")
    pivot = pivot.sort_values("Stopwords included", ascending=True)

    fig, ax = plt.subplots(figsize=(9, 5))
    pivot.plot(kind="barh", ax=ax, color=["#2f6f73", "#b45309"], edgecolor="#1f2933")
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("F1-score")
    ax.set_ylabel("Model")
    ax.set_title("Stopword Ablation: F1-score Comparison")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(title="Experiment", loc="lower right")

    for container in ax.containers:
        ax.bar_label(container, fmt="%.3f", fontsize=8, padding=3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)

    print("Saved:", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
