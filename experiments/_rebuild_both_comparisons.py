"""Rebuild all_models_comparison.csv for both experiments from the saved reports.

Each row is derived from that model's `classification_report_*.csv` (accuracy,
precision, recall, F1, macro-F1) plus its `roc_curve_*.csv` (ROC-AUC), so the CSV
can never drift from the artifacts on disk the way the previous hand-carried
`step9_metrics.csv` did.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from experiments.run_completion_pass import rebuild_comparison_from_reports

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = [
    "experiment_1_stopwords_included",
    "experiment_2_stopwords_removed",
]


def main() -> int:
    combined: list[dict[str, object]] = []
    for name in EXPERIMENTS:
        exp_dir = ROOT / "experiments" / name
        rows = rebuild_comparison_from_reports(exp_dir)
        out = exp_dir / "results" / "all_models_comparison.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out, index=False)
        print(f"== {name}: wrote {len(rows)} rows -> {out.relative_to(ROOT)} ==", flush=True)
        for row in rows:
            print(
                f"   {row['model']:<28} acc={float(row['accuracy']):.4f} "
                f"f1={float(row['f1']):.4f} roc_auc={row.get('roc_auc', 'n/a')}",
                flush=True,
            )
        combined.extend(rows)

    combined.sort(key=lambda r: (float(r["f1"]), float(r["accuracy"])), reverse=True)
    combined_df = pd.DataFrame(combined)
    for name in EXPERIMENTS:
        combined_path = ROOT / "experiments" / name / "results" / "two_experiment_model_comparison.csv"
        combined_df.to_csv(combined_path, index=False)
        print(f"== combined: wrote {len(combined)} rows -> {combined_path.relative_to(ROOT)} ==", flush=True)
    best = combined[0]
    print(f"== OVERALL BEST: {best['experiment']} / {best['model']} "
          f"acc={float(best['accuracy']):.4f} f1={float(best['f1']):.4f} ==", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
