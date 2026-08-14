from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def run(args: list[str]) -> None:
    print("\n== RUN:", " ".join(args), "==")
    subprocess.run([str(PYTHON), *args], cwd=ROOT, check=True)


def main() -> int:
    run(["experiments/run_full_12_steps.py", "--skip-xlm-r"])
    run(["train_all.py", "--force-all", "--skip-traditional", "--skip-deep", "--skip-outputs"])
    run(["experiments/run_completion_pass.py", "--skip-transformers", "--skip-embeddings", "--skip-tuning", "--skip-xai"])
    run(["experiments/build_balanced_refresh_report.py"])
    run(["experiments/regenerate_eda_images.py"])
    print("\nFull local refresh complete: models, metrics, reports, EDA images, and per-category AI-type images.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
