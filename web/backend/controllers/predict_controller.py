from __future__ import annotations

import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pymongo.errors import PyMongoError

from ..database.mongo import get_database
from ..models.prediction import PredictionDocument
from ..models.user import UserRole
from ..schemas.predict import (
    DocumentExtractResponse,
    LinkAnalysisRequest,
    LinkAnalysisResponse,
    PredictRequest,
    PredictResponse,
    PublishRequest,
)
from ..services.activity_service import log_activity
from ..services.ml_service import (
    InferenceError,
    ModelNotFoundError,
    NoModelsLoadedError,
    ml_service,
)
from ..services.category_service import category_service
from ..services import document_service, link_analysis_service
from ..services.document_service import DocumentError
from ..services.link_analysis_service import LinkFetchError
from ..utils.dependencies import get_current_user

router = APIRouter(tags=["predict"])

# Roughly one short paragraph — enough context for a meaningful AI-vs-human signal.
MIN_TEXT_LENGTH = 50

# Paragraph-level accuracy was measured on this model; reporting those figures
# beside labels from a different model would misdescribe them.
LINK_ANALYSIS_MODEL = "linear_svc_tfidf"

# An uploaded document below this is not worth classifying: the same floor the link
# path uses, so a 40-word memo is treated the same however it arrives.
MIN_DOCUMENT_WORDS = 30

_ALPHA_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_SOMALI_INDICATOR_WORDS: frozenset[str] | None = None
_ENGLISH_ONLY_WORDS: frozenset[str] | None = None

# Common English function words. Real Somali prose has ~0 of these; even a
# short English passage embedded in otherwise-Somali text lights this up.
_ENGLISH_INDICATOR_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "so", "as", "of", "in", "on", "at", "to", "for",
    "with", "from", "by", "this", "that", "these", "those", "it", "its",
    "he", "she", "they", "we", "you", "i", "his", "her", "their", "our",
    "has", "have", "had", "will", "would", "can", "could", "not", "no",
    "more", "most", "than", "into", "about", "which", "what", "when", "how",
})


def _somali_indicator_words() -> frozenset[str]:
    """Lazily load the project's curated Somali function-word list — real Somali
    text of any length reliably contains several of these; other languages don't."""
    global _SOMALI_INDICATOR_WORDS
    if _SOMALI_INDICATOR_WORDS is None:
        # Straight from the module that defines the 483 words, not from
        # run_stopword_ablation, which merely re-exports them: that is a research
        # script and imports matplotlib, seaborn and yaml at module level. Pulling
        # a word list through it made every prediction on a server without those
        # plotting libraries fail with ModuleNotFoundError.
        from experiments.somali_stopwords import SOMALI_FUNCTION_WORDS

        _SOMALI_INDICATOR_WORDS = frozenset(SOMALI_FUNCTION_WORDS)
    return _SOMALI_INDICATOR_WORDS


def _english_only_words() -> frozenset[str]:
    """English function words that are not also Somali ones.

    `a`, `in` and `is` are ordinary Somali function words as well as English ones --
    "sheegtay in ...", "is barbardhig" -- so counting them as evidence of English made
    genuine Somali news articles fail the language check outright.
    """
    global _ENGLISH_ONLY_WORDS
    if _ENGLISH_ONLY_WORDS is None:
        _ENGLISH_ONLY_WORDS = frozenset(_ENGLISH_INDICATOR_WORDS - _somali_indicator_words())
    return _ENGLISH_ONLY_WORDS


def _looks_somali(text: str) -> bool:
    all_tokens = _TOKEN_RE.findall(text)
    alpha_words = [w.lower() for w in _ALPHA_WORD_RE.findall(text)]

    # Reject content that isn't mostly actual words (e.g. runs of numbers,
    # "1, 2, 3, ... 100" has plenty of tokens but zero letter-words).
    if len(all_tokens) >= 8 and len(alpha_words) < 0.5 * len(all_tokens):
        return False
    if len(alpha_words) < 8:
        # Too short for the statistical check to be meaningful either way —
        # let the MIN_TEXT_LENGTH check handle short/low-content inputs instead.
        return len(all_tokens) > 0

    somali_hits = sum(1 for w in alpha_words if w in _somali_indicator_words())
    english_hits = sum(1 for w in alpha_words if w in _english_only_words())
    somali_ratio = somali_hits / len(alpha_words)
    english_ratio = english_hits / len(alpha_words)

    # Real Somali prose is dense with function words (ee, oo, ayaa, waxaa, ...);
    # require at least ~8% of words to match. Also reject if English function
    # words are more than a token presence (~4%) — catches mixed-language input
    # even when the Somali portion alone would clear the 8% floor.
    return somali_ratio >= 0.08 and english_ratio < 0.04


def _auto_title(text: str) -> str:
    """Derive a headline from the first ~70 chars of a post, cut at a word boundary."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= 70:
        return cleaned
    truncated = cleaned[:70].rsplit(" ", 1)[0]
    return f"{truncated}…"


async def _check_and_increment_quota(user_id: str, db) -> None:
    """Record that this user made a prediction. Nothing is refused.

    Predictions are unlimited for every role. The counters are still kept, because the
    admin and analytics pages report them and the daily series would flatten to zero
    without them -- but they are a record of use, not a budget to spend. A stored limit
    from before this change is ignored rather than migrated, so an old row cannot start
    blocking a user again.
    """
    from bson import ObjectId

    if not user_id or not ObjectId.is_valid(user_id):
        return

    today_str = date.today().isoformat()
    month_str = datetime.now(timezone.utc).strftime("%Y-%m")

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return

    # The counters still roll over, so "today" and "this month" keep their meaning on
    # the dashboards even though neither is enforced.
    reset: dict = {}
    if user.get("last_count_reset") != today_str:
        reset["daily_prediction_count"] = 0
        reset["last_count_reset"] = today_str
    if user.get("last_month_reset") != month_str:
        reset["monthly_prediction_count"] = 0
        reset["last_month_reset"] = month_str
    if reset:
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": reset})

    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$inc": {"daily_prediction_count": 1, "monthly_prediction_count": 1}},
    )


@router.post("/predict", response_model=PredictResponse)
async def predict(
    req: PredictRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()

    # Enforce quota
    await _check_and_increment_quota(current_user.get("id", ""), db)

    # Enforce text length limits
    stripped_len = len(req.text.strip())
    if stripped_len < MIN_TEXT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Please enter at least one full paragraph ({MIN_TEXT_LENGTH}+ characters) "
                "so the model has enough context to classify the text reliably."
            ),
        )
    if not _looks_somali(req.text):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "This classifier only supports Somali text. The text you entered "
                "doesn't look like Somali — please check the language and try again."
            ),
        )

    try:
        out = ml_service.predict(req.text, req.model)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except NoModelsLoadedError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except InferenceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    cat_result = category_service.predict(req.text)

    # Archive a cleaned copy for potential use growing future training datasets.
    # Uses the exact same clean_text() as the training pipeline so this archive
    # can be merged into a future retrain without extra preprocessing.
    try:
        from experiments.run_balanced_experiments import clean_text as _pipeline_clean_text

        await db.submitted_articles.insert_one({
            "text": _pipeline_clean_text(req.text),
            "predicted_label": out["prediction"],
            "confidence": out.get("confidence"),
            "category": cat_result.get("category"),
            "model": out.get("model"),
            "source": "user_submission",
            "reviewed": False,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass  # archiving is best-effort — never block a live prediction on it

    publish_now = bool(req.publish)
    prediction = PredictionDocument(
        text=req.text,
        prediction=out["prediction"],
        confidence=out.get("confidence"),
        probabilities=out.get("probabilities", {}),
        model=out.get("model"),
        category=cat_result.get("category"),
        category_icon=cat_result.get("icon"),
        user_id=current_user.get("id", ""),
        user_email=current_user.get("email", ""),
        title=(req.title or "").strip() or (_auto_title(req.text) if publish_now else None),
        is_published=publish_now,
        author_name=(current_user.get("name") or current_user.get("email")) if publish_now else None,
        published_at=datetime.now(timezone.utc) if publish_now else None,
    )
    history_saved = True
    prediction_id: str | None = None
    try:
        insert_result = await db.predictions.insert_one(prediction.model_dump())
        prediction_id = str(insert_result.inserted_id)
    except (RuntimeError, PyMongoError):
        history_saved = False

    # Async audit log (fire-and-forget style via try/except)
    try:
        await log_activity(
            user_id=current_user.get("id", ""),
            user_email=current_user.get("email", ""),
            user_name=current_user.get("name", ""),
            action="prediction_made",
            category="prediction",
            details={
                "model": out.get("model"),
                "prediction": out["prediction"],
                "confidence": round(out.get("confidence", 0) * 100, 1),
                "text_length": len(req.text),
            },
        )
    except Exception:
        pass

    return {
        "prediction": out["prediction"],
        "label": out["prediction"],
        "score": out.get("confidence"),
        "confidence": out.get("confidence"),
        "probabilities": out.get("probabilities", {}),
        "model": out["model"],
        "history_saved": history_saved,
        "category": cat_result["category"],
        "category_icon": cat_result["icon"],
        "prediction_id": prediction_id,
    }


def _can_manage_post(doc: dict, current_user: dict) -> bool:
    if str(doc.get("user_id") or "") == str(current_user.get("id") or ""):
        return True
    return current_user.get("role") in {UserRole.ADMIN, UserRole.SUPER_ADMIN}


@router.patch("/predict/{prediction_id}/publish")
async def publish_prediction(
    prediction_id: str,
    req: PublishRequest,
    current_user: dict = Depends(get_current_user),
):
    """Publish an already-run prediction as a News Feed post."""
    from bson import ObjectId

    if not ObjectId.is_valid(prediction_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found.")

    db = get_database()
    doc = await db.predictions.find_one({"_id": ObjectId(prediction_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found.")
    if not _can_manage_post(doc, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only publish your own predictions.")

    title = (req.title or "").strip() or doc.get("title") or _auto_title(doc.get("text", ""))
    author_name = current_user.get("name") or current_user.get("email")
    published_at = datetime.now(timezone.utc)

    await db.predictions.update_one(
        {"_id": ObjectId(prediction_id)},
        {"$set": {
            "is_published": True,
            "title": title,
            "author_name": author_name,
            "published_at": published_at,
        }},
    )
    return {
        "id": prediction_id,
        "title": title,
        "author_name": author_name,
        "published_at": published_at.isoformat(),
    }


@router.delete("/predict/{prediction_id}/publish")
async def unpublish_prediction(
    prediction_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove a post from the News Feed without deleting the underlying prediction record."""
    from bson import ObjectId

    if not ObjectId.is_valid(prediction_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found.")

    db = get_database()
    doc = await db.predictions.find_one({"_id": ObjectId(prediction_id)})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found.")
    if not _can_manage_post(doc, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only unpublish your own posts.")

    await db.predictions.update_one(
        {"_id": ObjectId(prediction_id)},
        {"$set": {"is_published": False}},
    )
    return {"id": prediction_id, "is_published": False}


@router.get("/predict/feed")
async def get_news_feed(
    limit: int = 30,
    category: str = "",
    current_user: dict = Depends(get_current_user),
):
    """Blog-style feed of posts users have explicitly published from their
    predictions — visible to every logged-in user. Publishing is opt-in, so
    the full text and author are shown (unlike the raw prediction history)."""
    db = get_database()
    limit = max(1, min(limit, 100))
    query: dict = {"is_published": True}
    if category:
        query["category"] = category

    cursor = db.predictions.find(query).sort("published_at", -1).limit(limit)
    items = []
    async for d in cursor:
        text = d.get("text", "")
        items.append({
            "id": str(d["_id"]),
            "title": d.get("title") or _auto_title(text),
            "text": text,
            "prediction": d.get("prediction"),
            "confidence": d.get("confidence"),
            "category": d.get("category"),
            "category_icon": d.get("category_icon"),
            "model": d.get("model"),
            "user_id": d.get("user_id"),
            "author_name": d.get("author_name") or d.get("user_email"),
            "created_at": d["created_at"].isoformat() if d.get("created_at") else None,
            "published_at": d["published_at"].isoformat() if d.get("published_at") else None,
        })
    return {"items": items}



def _accuracy_note(model_key: str, breakdown: dict) -> str:
    """Describe, in the reader's terms, how far the proportion can be trusted.

    The figures are read from the measurement for the model that produced the labels,
    so switching model changes the caveat as well as the result.
    """
    if not breakdown.get("accuracy_measured"):
        return (
            "Paragraph-level accuracy has not been measured for this model, so the "
            "proportion below is shown without a per-paragraph confidence. The "
            "whole-article verdict remains the reliable figure."
        )
    short = link_analysis_service.accuracy_for(30, model_key)
    mid = link_analysis_service.accuracy_for(80, model_key)
    long = link_analysis_service.accuracy_for(200, model_key)
    measured = (
        f"Measured on held-out data for this model: {short:.1%} accurate on a 30-word "
        f"paragraph, {mid:.1%} at 80 words, {long:.1%} at 200."
    )
    if breakdown.get("short_article"):
        # A short item is analysed rather than refused, but the reader is told how thin
        # the evidence is -- otherwise a "100% AI" proportion drawn from one or two
        # blocks of text reads as far stronger evidence than it is.
        scored = breakdown.get("paragraphs_scored", 0)
        basis = (
            "it was scored as a single block rather than split into paragraphs"
            if scored <= 1 else
            f"only {scored} paragraphs were long enough to score"
        )
        return (
            f"{measured} This article is short, so {basis}. A human/AI proportion "
            "drawn from that little text would overstate what was measured, so the "
            "whole-article verdict above is the figure to read; accuracy is lowest on "
            "short text, so treat it as indicative rather than settled."
        )
    return (
        f"{measured} Because short paragraphs are the least reliable, any under "
        f"{link_analysis_service.MIN_PARAGRAPH_WORDS} words are excluded from the "
        "proportion rather than allowed to swing it. The whole-article verdict above "
        "is the more dependable of the two figures."
    )


@router.post("/analyze-link", response_model=LinkAnalysisResponse)
async def analyze_link(
    req: LinkAnalysisRequest,
    current_user: dict = Depends(get_current_user),
):
    """Fetch an article by URL and report its category and how much of it reads as AI.

    The whole-article verdict is the headline because that is the figure measured at
    94.79%. The paragraph proportion is reported alongside it, with the accuracy that
    actually applies at paragraph length -- 79.4% at 30 words, 92.0% at 120 -- rather
    than the document-level figure, which would overstate it.
    """
    db = get_database()
    await _check_and_increment_quota(current_user.get("id", ""), db)

    try:
        title, text, paragraphs = link_analysis_service.fetch(req.url)
    except LinkFetchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Somali news sites commonly close an article with an English "about us" blurb.
    # It is not article text, a Somali classifier has nothing useful to say about it,
    # and left in place it dragged whole articles below the language threshold.
    somali_paragraphs = [p for p in paragraphs if _looks_somali(p)]
    if somali_paragraphs and len(" ".join(somali_paragraphs).split()) >= link_analysis_service.MIN_ARTICLE_WORDS:
        paragraphs = somali_paragraphs
        text = "\n\n".join(paragraphs)

    words = len(text.split())
    if words < link_analysis_service.MIN_ARTICLE_WORDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"That page holds only {words} words of article text — too little for "
                f"the classifier to say anything meaningful. At least "
                f"{link_analysis_service.MIN_ARTICLE_WORDS} words are needed."
            ),
        )
    if not _looks_somali(text):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "The article at that address does not look like Somali. This classifier "
                "was trained on Somali only, so its output there would be meaningless."
            ),
        )

    # Default to LinearSVC: it is the champion at 94.79%, and it is the model whose
    # paragraph-level accuracy was measured, so the per-paragraph confidence reported
    # below describes the model that actually produced the labels.
    model_key = req.model or LINK_ANALYSIS_MODEL
    try:
        out = ml_service.predict(text, model_key)
        breakdown = link_analysis_service.analyse(
            paragraphs,
            lambda batch: ml_service.predict_batch(batch, model_key),
            model_key,
        )
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except NoModelsLoadedError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except InferenceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    category = category_service.predict(text)

    # Keyword-only signature, and a failure to log must not lose the user's result.
    try:
        await log_activity(
            user_id=current_user.get("id", ""),
            user_email=current_user.get("email", ""),
            user_name=current_user.get("name", ""),
            action="link_analysed",
            category="prediction",
            details={
                "url": req.url[:300],
                "model": out.get("model"),
                "prediction": out["prediction"],
                "ai_percent": breakdown["ai_percent"],
                "word_count": words,
            },
        )
    except Exception:  # noqa: BLE001 - logging is best-effort
        pass

    return LinkAnalysisResponse(
        url=req.url,
        title=title or None,
        word_count=words,
        prediction=out["prediction"],
        confidence=out.get("confidence"),
        probabilities=out.get("probabilities", {}),
        model=out.get("model", model_key),
        category=category.get("category"),
        category_icon=category.get("icon"),
        accuracy_note=_accuracy_note(model_key, breakdown),
        **breakdown,
    )


@router.post("/extract-document", response_model=DocumentExtractResponse)
async def extract_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Read a Word or PDF upload and return its Somali text for classification.

    Extraction is kept separate from prediction on purpose: the text is handed back so
    the reader can see what was actually pulled out of the file -- a PDF's text layer
    rarely matches its printed layout exactly -- and only then chooses to classify it.

    The upload is refused unless it is genuinely a `.docx` or `.pdf`, and unless the
    text reads as Somali. A classifier trained on Somali alone produces a confident
    label for English or Arabic too; that label just means nothing, so the input is
    rejected here rather than allowed to produce a meaningless verdict.
    """
    data = await file.read()
    try:
        suffix, text = document_service.extract(file.filename or "", data)
    except DocumentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    words = len(text.split())
    if words < MIN_DOCUMENT_WORDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"That document holds only {words} words of text — too little for the "
                f"classifier to say anything meaningful. At least {MIN_DOCUMENT_WORDS} "
                "words are needed."
            ),
        )
    if not _looks_somali(text):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "The text in that document does not look like Somali. This classifier "
                "was trained on Somali only, so its output there would be meaningless."
            ),
        )

    try:
        await log_activity(
            user_id=current_user.get("id", ""),
            user_email=current_user.get("email", ""),
            user_name=current_user.get("name", ""),
            action="document_uploaded",
            category="prediction",
            details={"filename": (file.filename or "")[:200], "type": suffix, "word_count": words},
        )
    except Exception:  # noqa: BLE001 - logging is best-effort
        pass

    return DocumentExtractResponse(
        filename=file.filename or f"document{suffix}",
        file_type=suffix.lstrip("."),
        word_count=words,
        char_count=len(text),
        paragraph_count=len([p for p in text.split("\n\n") if p.strip()]),
        text=text,
    )
