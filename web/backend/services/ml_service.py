import logging
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from ..config import settings

logger = logging.getLogger(__name__)


class ModelNotFoundError(KeyError):
    pass


class NoModelsLoadedError(RuntimeError):
    pass


class InferenceError(RuntimeError):
    pass

class MLService:
    def __init__(self):
        self.models: dict[str, Any] = {}
        self.model_paths: dict[str, str] = {}
        self.load_errors: dict[str, str] = {}
        self.load_models()

    def load_models(self) -> None:
        self.models = {}
        self.model_paths = {}
        self.load_errors = {}

        for path in self._discover_linear_svc_artifacts():
            key = self._model_key(path)
            self._load_artifact(path, key)

        if self.models and "linear_svc_tfidf" not in self.models:
            first_key = next(iter(self.models))
            self.models["linear_svc_tfidf"] = self.models[first_key]
            self.model_paths["linear_svc_tfidf"] = self.model_paths[first_key]

    def list_models(self) -> list[str]:
        return list(self.models.keys())

    def _discover_linear_svc_artifacts(self) -> list[Path]:
        patterns = ("*LinearSVC*TFIDF*.joblib", "*linear*svc*tfidf*.joblib")
        candidates: list[Path] = []

        if settings.models_dir.exists():
            for pattern in patterns:
                candidates.extend(settings.models_dir.rglob(pattern))

        if not candidates and settings.experiments_dir.exists():
            for pattern in patterns:
                candidates.extend(settings.experiments_dir.rglob(pattern))

        return sorted(set(candidates))

    def _load_artifact(self, path: Path, key: str) -> None:
        try:
            model = joblib.load(path)
            if not hasattr(model, "predict"):
                raise TypeError("Artifact does not expose a predict method")
            self.models[key] = model
            self.model_paths[key] = str(path)
        except Exception as exc:
            self.load_errors[str(path)] = str(exc)
            logger.exception("Failed to load model artifact %s", path)

    def _model_key(self, path: Path) -> str:
        experiment = next(
            (part for part in path.parts if part.lower().startswith("experiment_")),
            None,
        )
        stem = path.stem.lower()
        if experiment:
            return f"{experiment}_{stem}".lower()
        return stem

    def predict(self, text: str, model_key: str | None = None) -> dict[str, Any]:
        if not self.models:
            raise NoModelsLoadedError("No LinearSVC TF-IDF models are loaded")
        if model_key is None:
            model_key = next(iter(self.models.keys()))
        model_key = model_key.strip().lower()
        model = self.models.get(model_key)
        if model is None:
            raise ModelNotFoundError(f"Model '{model_key}' was not found")

        try:
            input_values = [text]
            prediction = str(model.predict(input_values)[0])
            probabilities = self._probabilities(model, input_values, prediction)
            confidence = max(probabilities.values()) if probabilities else None
            return {
                "prediction": prediction,
                "confidence": confidence,
                "probabilities": probabilities,
                "model": model_key,
            }
        except Exception as exc:
            raise InferenceError("Unable to run inference for the provided text") from exc

    def _probabilities(
        self,
        model: Any,
        input_values: list[str],
        prediction: str,
    ) -> dict[str, float]:
        classes = [str(item) for item in getattr(model, "classes_", [])]
        if not classes and hasattr(model, "named_steps"):
            classifier = model.named_steps.get("clf")
            classes = [str(item) for item in getattr(classifier, "classes_", [])]

        if hasattr(model, "predict_proba"):
            raw_probabilities = model.predict_proba(input_values)[0]
            if not classes:
                classes = [str(index) for index in range(len(raw_probabilities))]
            return self._round_probabilities(classes, raw_probabilities)

        if hasattr(model, "decision_function"):
            scores = model.decision_function(input_values)
            raw_scores = np.asarray(scores[0] if np.ndim(scores) > 1 else scores)

            if raw_scores.ndim == 0 or raw_scores.size == 1:
                score = float(raw_scores.reshape(-1)[0])
                positive_probability = 1.0 / (1.0 + math.exp(-score))
                if len(classes) == 2:
                    return self._round_probabilities(
                        classes,
                        [1.0 - positive_probability, positive_probability],
                    )
                return {
                    prediction: round(positive_probability, 6),
                    "not_" + prediction: round(1.0 - positive_probability, 6),
                }

            probabilities = self._softmax(raw_scores.astype(float))
            if not classes:
                classes = [str(index) for index in range(len(probabilities))]
            return self._round_probabilities(classes, probabilities)

        return {prediction: 1.0}

    def _softmax(self, values: np.ndarray) -> np.ndarray:
        shifted = values - np.max(values)
        exp_values = np.exp(shifted)
        return exp_values / exp_values.sum()

    def _round_probabilities(
        self,
        classes: list[str],
        probabilities: Any,
    ) -> dict[str, float]:
        return {
            class_name: round(float(probability), 6)
            for class_name, probability in zip(classes, probabilities)
        }

ml_service = MLService()
