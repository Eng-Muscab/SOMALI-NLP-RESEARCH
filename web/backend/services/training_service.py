from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from ..config import REPO_ROOT


class TrainingStage(str, Enum):
    TRADITIONAL = "traditional"


class TrainingStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TrainingJob:
    stage: TrainingStage
    status: TrainingStatus = TrainingStatus.IDLE
    started_at: str | None = None
    finished_at: str | None = None
    message: str = ""
    log_tail: str = ""
    trained_models: int = 0
    return_code: int | None = None
    options: dict[str, bool] = field(default_factory=dict)


class TrainingService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self.job = TrainingJob(stage=TrainingStage.TRADITIONAL)

    @property
    def is_running(self) -> bool:
        return self.job.status == TrainingStatus.RUNNING

    def get_status(self) -> dict[str, object]:
        return {
            "stage": self.job.stage.value,
            "status": self.job.status.value,
            "started_at": self.job.started_at,
            "finished_at": self.job.finished_at,
            "message": self.job.message,
            "trained_models": self.job.trained_models,
            "return_code": self.job.return_code,
            "options": self.job.options,
            "log_tail": self.job.log_tail[-4000:],
        }

    async def start_traditional_training(
        self,
        *,
        all_traditional: bool = True,
        include_random_forest: bool = False,
        include_xgboost: bool = False,
    ) -> dict[str, object]:
        async with self._lock:
            if self.is_running:
                return {
                    "status": self.job.status.value,
                    "message": "Training is already running.",
                }

            self.job = TrainingJob(
                stage=TrainingStage.TRADITIONAL,
                status=TrainingStatus.RUNNING,
                started_at=datetime.now(timezone.utc).isoformat(),
                message="Traditional ML training started.",
                options={
                    "all_traditional": all_traditional,
                    "include_random_forest": include_random_forest,
                    "include_xgboost": include_xgboost,
                },
            )
            self._task = asyncio.create_task(
                self._run_traditional_training(
                    all_traditional=all_traditional,
                    include_random_forest=include_random_forest,
                    include_xgboost=include_xgboost,
                )
            )
            return self.get_status()

    async def _run_traditional_training(
        self,
        *,
        all_traditional: bool,
        include_random_forest: bool,
        include_xgboost: bool,
    ) -> None:
        script = REPO_ROOT / "experiments" / "train_from_splits.py"
        command = [sys.executable, str(script)]
        if all_traditional:
            command.append("--all-traditional")
        else:
            if include_random_forest:
                command.append("--include-random-forest")
            if include_xgboost:
                command.append("--include-xgboost")

        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                command,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
            self.job.log_tail = output
            self.job.return_code = completed.returncode
            self.job.finished_at = datetime.now(timezone.utc).isoformat()

            summary_path = REPO_ROOT / "experiments" / "train_from_splits_summary.json"
            if summary_path.exists():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                self.job.trained_models = int(summary.get("trained_models", 0))

            if completed.returncode == 0 and self.job.trained_models > 0:
                self.job.status = TrainingStatus.COMPLETED
                self.job.message = f"Training finished. {self.job.trained_models} model(s) saved."
            else:
                self.job.status = TrainingStatus.FAILED
                self.job.message = output[-500:] or "Training failed without output."
        except Exception as exc:
            self.job.status = TrainingStatus.FAILED
            self.job.finished_at = datetime.now(timezone.utc).isoformat()
            self.job.message = str(exc)
            self.job.return_code = 1


training_service = TrainingService()
