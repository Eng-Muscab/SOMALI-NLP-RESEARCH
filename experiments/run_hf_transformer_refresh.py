from __future__ import annotations

from pathlib import Path

from experiments.run_completion_pass import TRANSFORMER_SPECS, train_hf_transformer
from experiments.run_full_12_steps import train_xlmr


EXPERIMENTS = ["experiment_1_stopwords_included", "experiment_2_stopwords_removed"]
LABEL_NAMES = ["AI", "HUMAN"]
SEED = 42


def report_exists(exp_dir: Path, model_name: str) -> bool:
    return (exp_dir / "evaluation" / "reports" / f"classification_report_{model_name}.csv").exists()


def main() -> int:
    for exp_name in EXPERIMENTS:
        exp_dir = Path("experiments") / exp_name
        if not report_exists(exp_dir, "XLMRoberta_FineTuned"):
            print(f"== {exp_name}: XLMRoberta_FineTuned ==")
            print(train_xlmr(exp_dir, LABEL_NAMES, SEED))
        else:
            print(f"== {exp_name}: XLMRoberta_FineTuned already complete ==")

        for model_id, model_name in TRANSFORMER_SPECS:
            if report_exists(exp_dir, model_name):
                print(f"== {exp_name}: {model_name} already complete ==")
                continue
            print(f"== {exp_name}: {model_name} ==")
            print(train_hf_transformer(exp_dir, LABEL_NAMES, SEED, model_id, model_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
