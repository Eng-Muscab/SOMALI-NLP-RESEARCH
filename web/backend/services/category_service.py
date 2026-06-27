"""Article category classifier trained on the raw Somali NLP dataset.

Categories: Politics, Sports, Education, Business, Technology, Religion, Health, Entertainment.
Uses TF-IDF + LinearSVC, trained lazily on first prediction call and cached in memory.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "Business", "Education", "Entertainment",
    "Health", "Politics", "Religion", "Sports", "Technology",
]

_ICONS: dict[str, str] = {
    "Politics":      "🏛️",
    "Sports":        "⚽",
    "Education":     "📚",
    "Business":      "💼",
    "Technology":    "💻",
    "Religion":      "🕌",
    "Health":        "🏥",
    "Entertainment": "🎬",
}


class CategoryService:
    def __init__(self) -> None:
        self._model = None
        self._vectorizer = None
        self._lock = threading.Lock()
        self._trained = False
        self._model_cache: Path | None = None

    # ── internal helpers ──────────────────────────────────────────────────────

    def _data_path(self) -> Path:
        from ..config import REPO_ROOT
        return REPO_ROOT / "data" / "raw" / "full_dataset.csv"

    def _cache_path(self) -> Path:
        from ..config import REPO_ROOT
        return REPO_ROOT / "models" / "category_classifier.joblib"

    def _train(self) -> None:
        import joblib
        import pandas as pd
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.svm import LinearSVC
        from sklearn.pipeline import Pipeline

        csv_path = self._data_path()
        if not csv_path.exists():
            logger.warning("Category classifier: dataset not found at %s", csv_path)
            return

        df = pd.read_csv(csv_path, usecols=["Text", "Category"])
        df["Category"] = df["Category"].str.strip().str.title()
        # Keep only known categories
        df = df[df["Category"].isin(_CATEGORIES)].dropna(subset=["Text"])
        df = df[df["Text"].str.len() > 30]

        if len(df) < 50:
            logger.warning("Category classifier: not enough data (%d rows)", len(df))
            return

        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                analyzer="char_wb", ngram_range=(3, 5),
                max_features=60_000, sublinear_tf=True,
            )),
            ("clf", LinearSVC(C=1.0, max_iter=2000)),
        ])
        pipeline.fit(df["Text"].tolist(), df["Category"].tolist())

        cache = self._cache_path()
        cache.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, cache)
        self._model = pipeline
        logger.info("Category classifier trained and cached (%d samples, %d classes)", len(df), len(_CATEGORIES))

    def _load_or_train(self) -> None:
        import joblib
        cache = self._cache_path()
        if cache.exists():
            try:
                self._model = joblib.load(cache)
                logger.info("Category classifier loaded from cache.")
                return
            except Exception as exc:
                logger.warning("Category classifier cache invalid (%s), retraining.", exc)
        self._train()

    def _ensure_ready(self) -> bool:
        if self._trained:
            return self._model is not None
        with self._lock:
            if not self._trained:
                self._load_or_train()
                self._trained = True
        return self._model is not None

    # ── public API ────────────────────────────────────────────────────────────

    def predict(self, text: str) -> dict:
        """Return {'category': str, 'icon': str} or {'category': 'Unknown', 'icon': '📄'}."""
        if not self._ensure_ready() or self._model is None:
            return {"category": "Unknown", "icon": "📄"}
        try:
            cat = self._model.predict([text])[0]
            return {"category": cat, "icon": _ICONS.get(cat, "📄")}
        except Exception as exc:
            logger.warning("Category prediction failed: %s", exc)
            return {"category": "Unknown", "icon": "📄"}

    def retrain(self) -> None:
        """Force retrain (e.g., after dataset update)."""
        cache = self._cache_path()
        if cache.exists():
            cache.unlink()
        with self._lock:
            self._trained = False
        self._ensure_ready()


category_service = CategoryService()
