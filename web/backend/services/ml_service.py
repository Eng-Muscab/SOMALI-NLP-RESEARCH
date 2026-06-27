import logging
import math
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from ..config import settings

logger = logging.getLogger(__name__)

# Ensure project root is importable (for experiments.run_full_12_steps)
_project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import TransformerBlock at module level so the @register_keras_serializable
# decorator runs and registers the class before any .keras model is loaded.
try:
    from experiments.transformer_block import TransformerBlock as _TransformerBlock  # noqa: F401
    logger.info("TransformerBlock registered for Keras serialization.")
except Exception as _e:
    logger.warning("Could not pre-register TransformerBlock: %s", _e)
    _TransformerBlock = None


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

        for path in self._discover_model_artifacts():
            key = self._model_key(path)
            self._load_artifact(path, key)

        if self.models and "linear_svc_tfidf" not in self.models:
            linear_key = next((key for key in self.models if key.endswith("linearsvc_tfidf")), None)
            if linear_key:
                self.models["linear_svc_tfidf"] = self.models[linear_key]
                self.model_paths["linear_svc_tfidf"] = self.model_paths[linear_key]

    def list_models(self) -> list[str]:
        return list(self.models.keys())

    def _discover_model_artifacts(self) -> list[Path]:
        patterns = ["*.joblib"]
        if settings.load_deep_models:
            patterns.extend(["*.keras", "model.safetensors", "pytorch_model.bin"])
        candidates: list[Path] = []

        if settings.experiments_dir.exists():
            for pattern in patterns:
                candidates.extend(settings.experiments_dir.rglob(pattern))

        valid_candidates = []
        for c in candidates:
            parts = {part.lower() for part in c.parts}
            if "tokenizer" in c.name.lower():
                continue
            if c.suffix == ".joblib" and "models" not in parts:
                continue
            valid_candidates.append(c)

        return sorted(set(valid_candidates))

    def _load_artifact(self, path: Path, key: str) -> None:
        try:
            if path.suffix == ".joblib":
                model = joblib.load(path)
                if not hasattr(model, "predict"):
                    raise TypeError("Artifact does not expose a predict method")
                self.models[key] = {"type": "sklearn", "model": model}
                self.model_paths[key] = str(path)
            elif path.suffix == ".keras":
                import tensorflow as tf
                model = tf.keras.models.load_model(path, compile=False)
                self.models[key] = {"type": "keras", "model": model}
                self.model_paths[key] = str(path)
            elif path.name in ["model.safetensors", "pytorch_model.bin"]:
                from transformers import pipeline
                model = pipeline("text-classification", model=str(path.parent))
                key = self._model_key(path.parent)
                self.models[key] = {"type": "transformers", "model": model}
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
            raise NoModelsLoadedError("No models are loaded")
        if model_key is None:
            model_key = next(iter(self.models.keys()))
        model_key = model_key.strip().lower()
        model_data = self.models.get(model_key)
        
        if model_data is None:
            raise ModelNotFoundError(f"Model '{model_key}' was not found")

        try:
            input_values = [text]
            model_type = model_data["type"]
            model = model_data["model"]

            if model_type == "sklearn":
                raw_pred = model.predict(input_values)[0]
                prediction = self._map_prediction(model_type, raw_pred)
                probabilities = self._probabilities(model, input_values, prediction)
                confidence = max(probabilities.values()) if probabilities else None
            elif model_type == "keras":
                import joblib
                from tensorflow.keras.preprocessing.sequence import pad_sequences
                
                experiment_dir = Path(self.model_paths[model_key]).parents[2]
                tokenizer_path = experiment_dir / "data" / "tokenizer.joblib"
                
                if tokenizer_path.exists():
                    tok_meta = joblib.load(tokenizer_path)
                    tokenizer = tok_meta["tokenizer"]
                    max_length = tok_meta["max_length"]
                    classes = tok_meta.get("classes", ["AI", "HUMAN"])
                    sequences = tokenizer.texts_to_sequences(input_values)
                    padded = pad_sequences(sequences, maxlen=max_length, padding="post", truncating="post")
                    
                    raw_probs = model.predict(padded, verbose=0)[0]
                    pred_idx = int(np.argmax(raw_probs))
                    prediction = self._map_prediction(model_type, classes[pred_idx] if pred_idx < len(classes) else str(pred_idx))
                    probabilities = {
                        self._map_prediction(model_type, classes[i] if i < len(classes) else i): float(p)
                        for i, p in enumerate(raw_probs)
                    }
                    confidence = float(np.max(raw_probs))
                else:
                    raise InferenceError("Tokenizer not found for Keras model")
            elif model_type == "transformers":
                result = model(text)[0]
                raw_label = result["label"]
                prediction = self._map_prediction(model_type, raw_label)
                confidence = float(result["score"])
                probabilities = {prediction: confidence}

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
            self._map_prediction("sklearn", class_name): round(float(probability), 6)
            for class_name, probability in zip(classes, probabilities)
        }

    def _map_prediction(self, model_type: str, raw_pred: Any) -> str:
        """Map raw predictions to human‑readable labels.
        For binary models we assume 0 → AI, 1 → HUMAN.
        For Keras we may receive either an index or a label string.
        For Transformers we standardise common label patterns.
        """
        if model_type == "sklearn":
            return "AI" if str(raw_pred) == "0" else "HUMAN"
        if model_type == "keras":
            if isinstance(raw_pred, str):
                return raw_pred
            return "AI" if int(raw_pred) == 0 else "HUMAN"
        if model_type == "transformers":
            label = str(raw_pred).upper()
            if label in {"LABEL_0", "0"}:
                return "AI"
            if label in {"LABEL_1", "1"}:
                return "HUMAN"
            if "AI" in label:
                return "AI"
            if "HUMAN" in label:
                return "HUMAN"
            return label
        return str(raw_pred)

ml_service = MLService()
