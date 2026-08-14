import csv
import gc
import logging
import math
import os
import re
import sys
from collections import OrderedDict
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

class _ModelRegistry(dict):
    """A dict over the model catalogue that materialises deep models on access.

    The service treats `ml_service.models` as a plain mapping of key -> loaded model,
    and several call sites read it directly. Keeping that interface while loading
    lazily means the laziness lives here rather than in every caller.
    """

    def __init__(self, service: "MLService"):
        super().__init__()
        self._service = service

    def __getitem__(self, key):
        return self._service.get_model(key)

    def get(self, key, default=None):
        try:
            return self._service.get_model(key)
        except Exception:  # noqa: BLE001 - a failed load reads as absent
            return default

    def __contains__(self, key):
        return key in self._service.catalogue

    def __iter__(self):
        return iter(self._service.catalogue)

    def __len__(self):
        return len(self._service.catalogue)

    def keys(self):
        return self._service.catalogue.keys()

    def values(self):
        return [self._service.get_model(k) for k in self._service.catalogue]

    def items(self):
        return [(k, self._service.get_model(k)) for k in self._service.catalogue]


class MLService:
    """Serves every published classifier without holding them all in memory at once.

    Loading all 26 models eagerly costs ~2.3 GB at rest and ~5.4 GB once each has run
    an inference, because a transformer pipeline allocates its working buffers on first
    use. That does not fit a small VPS, and it buys nothing: a request uses one model.

    So the catalogue -- every model's key and path -- is built at start-up and is what
    `/models` reports, but only the sklearn models are resident. Those are 53 MB in
    total, they back the default prediction and the whole link-analysis path, and
    keeping them warm is what makes a paragraph sweep take 2 seconds rather than a
    minute. Deep models are loaded when first selected and held in a small
    most-recently-used set; asking for a third evicts the least recently used.

    Trade: the first request for a cold transformer pays its load time (~2-4 s), and
    a Keras model ~5 s. Every subsequent request on that model is served from memory.
    Set MAX_RESIDENT_DEEP_MODELS higher on a larger machine to widen the warm set.
    """

    # Two deep models resident is enough for a person comparing one against another,
    # and keeps the peak within reach of a 6 GB box.
    MAX_RESIDENT_DEEP_MODELS = int(os.getenv("MAX_RESIDENT_DEEP_MODELS", "2"))

    def __init__(self):
        # key -> (path, kind); the full published set, built without loading anything.
        self.catalogue: dict[str, tuple[Path, str]] = {}
        self.model_paths: dict[str, str] = {}
        self.load_errors: dict[str, str] = {}
        self._resident: OrderedDict[str, Any] = OrderedDict()
        self.models = _ModelRegistry(self)
        self.load_models()

    def load_models(self) -> None:
        """Build the catalogue and load the small models. Deep ones wait to be asked for."""
        self.catalogue = {}
        self.model_paths = {}
        self.load_errors = {}
        self._resident = OrderedDict()

        for path in self._discover_model_artifacts():
            kind = (
                "sklearn" if path.suffix == ".joblib"
                else "keras" if path.suffix == ".keras"
                else "transformers"
            )
            key = self._model_key(path.parent if kind == "transformers" else path)
            self.catalogue[key] = (path, kind)
            self.model_paths[key] = str(path)

        if self.catalogue and "linear_svc_tfidf" not in self.catalogue:
            linear_key = next((k for k in self.catalogue if k.endswith("linearsvc_tfidf")), None)
            if linear_key:
                self.catalogue["linear_svc_tfidf"] = self.catalogue[linear_key]
                self.model_paths["linear_svc_tfidf"] = self.model_paths[linear_key]

        # sklearn models stay resident: they are small, and the link-analysis path
        # batches hundreds of paragraphs through one of them per request.
        for key, (path, kind) in self.catalogue.items():
            if kind == "sklearn":
                self._materialise(key, path, kind, evictable=False)

        logger.info(
            "catalogue holds %d models; %d resident at start-up",
            len(self.catalogue), len(self._resident),
        )

    def get_model(self, key: str) -> Any:
        """Return the loaded model for `key`, loading and making room if needed."""
        entry = self._resident.get(key)
        if entry is not None:
            self._resident.move_to_end(key)
            return entry
        if key not in self.catalogue:
            raise ModelNotFoundError(f"Model '{key}' was not found")
        path, kind = self.catalogue[key]
        return self._materialise(key, path, kind, evictable=True)

    def _materialise(self, key: str, path: Path, kind: str, *, evictable: bool) -> Any:
        if evictable:
            self._evict_until_room()
        self._load_artifact(path, key)
        entry = self._resident.get(key)
        if entry is None:
            raise ModelNotFoundError(f"Model '{key}' could not be loaded")
        return entry

    def _evict_until_room(self) -> None:
        """Drop least-recently-used deep models until one more will fit."""
        deep = [k for k, v in self._resident.items() if v.get("type") in {"keras", "transformers"}]
        while len(deep) >= self.MAX_RESIDENT_DEEP_MODELS:
            oldest = deep.pop(0)
            self._resident.pop(oldest, None)
            logger.info("evicted %s to make room", oldest)
        if deep or True:
            gc.collect()

    def list_models(self) -> list[str]:
        """Every published model, whether or not it is currently in memory."""
        return list(self.catalogue.keys())

    def model_type(self, key: str) -> str | None:
        """The family a model belongs to, answered from the catalogue.

        `/models` reports the type of all 26 on every request. Answering that by
        touching `models[key]` would load each one and undo the point of loading
        lazily, so the type is read from the catalogue instead.
        """
        entry = self.catalogue.get(key)
        return entry[1] if entry else None

    def is_resident(self, key: str) -> bool:
        """Whether this model is currently in memory (diagnostics, not correctness)."""
        return key in self._resident

    def _discover_model_artifacts(self) -> list[Path]:
        patterns = ["*.joblib"]
        if settings.load_deep_models:
            patterns.extend(["*.keras", "model.safetensors", "pytorch_model.bin"])
        candidates: list[Path] = []

        if settings.experiments_dir.exists():
            for pattern in patterns:
                candidates.extend(settings.experiments_dir.rglob(pattern))

        published = self._published_model_names()
        valid_candidates = []
        for c in candidates:
            parts = {part.lower() for part in c.parts}
            if "tokenizer" in c.name.lower():
                continue
            if c.suffix == ".joblib" and "models" not in parts:
                continue
            # Only artefacts the UI actually offers. The experiments directory also
            # holds re-run leftovers (`*_balanced_refresh`) and models that never made
            # the comparison table; loading them cost 6 GB of RAM for classifiers no
            # one could select, which is the difference between fitting a small VPS
            # and not. The comparison CSV is the single source of truth for what is
            # published, so it decides what is loaded.
            if published and not self._is_published(c, published):
                continue
            valid_candidates.append(c)

        return sorted(set(valid_candidates))

    @staticmethod
    def _normalise(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    def _published_model_names(self) -> set[str]:
        """Model names listed in the per-experiment comparison CSVs.

        Returns an empty set if no CSV can be read, and the caller then falls back to
        loading everything -- a missing results file should degrade to the old
        behaviour rather than leave the platform with no models at all.
        """
        names: set[str] = set()
        paths = list(settings.experiments_dir.glob("experiment_*/results/all_models_comparison.csv"))
        for path in paths:
            try:
                with path.open(newline="", encoding="utf-8") as fh:
                    for row in csv.DictReader(fh):
                        name = (row.get("model") or row.get("Model") or "").strip()
                        if name:
                            names.add(self._normalise(name))
            except OSError:
                logger.warning("could not read %s while deciding what to load", path)
        return names

    def _is_published(self, path: Path, published: set[str]) -> bool:
        """Does this artefact back one of the published models?

        A transformer is a directory of files, so `model.safetensors` is matched on its
        parent directory; everything else is matched on its own stem.
        """
        candidate = path.parent.name if path.name in {"model.safetensors", "pytorch_model.bin"} else path.stem
        normalised = self._normalise(candidate)
        if normalised in published:
            return True
        # XLMRoberta_FineTuned is stored in a directory named after the base checkpoint.
        return normalised in {"xlmrobertabase"} and "xlmrobertafinetuned" in published

    def _load_artifact(self, path: Path, key: str) -> None:
        try:
            if path.suffix == ".joblib":
                model = joblib.load(path)
                if not hasattr(model, "predict"):
                    raise TypeError("Artifact does not expose a predict method")
                self._resident[key] = {"type": "sklearn", "model": model}
            elif path.suffix == ".keras":
                import tensorflow as tf
                model = tf.keras.models.load_model(path, compile=False)
                self._resident[key] = {"type": "keras", "model": model}
            elif path.name in ["model.safetensors", "pytorch_model.bin"]:
                from transformers import pipeline
                model = pipeline("text-classification", model=str(path.parent))
                self._resident[key] = {"type": "transformers", "model": model}
            self.model_paths.setdefault(key, str(path))
            self._resident.move_to_end(key)
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


    def predict_batch(self, texts: list[str], model_key: str | None = None) -> list[str]:
        """Label many texts in one call.

        Segment analysis classifies every paragraph of an article. Calling predict()
        once per paragraph re-enters the whole inference path each time -- on a Keras
        model that took over a minute for five paragraphs. A sklearn pipeline vectorises
        and predicts a whole list in one pass, so that path is taken where available and
        the per-item loop is kept only as a fallback.
        """
        if not self.models:
            raise NoModelsLoadedError("No models are loaded")
        key = (model_key or next(iter(self.models.keys()))).strip().lower()
        model_data = self.models.get(key)
        if model_data is None:
            raise ModelNotFoundError(f"Model '{key}' was not found")

        if model_data["type"] == "sklearn":
            raw = model_data["model"].predict(list(texts))
            return [self._map_prediction("sklearn", value) for value in raw]
        return [self.predict(text, key)["prediction"] for text in texts]

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
