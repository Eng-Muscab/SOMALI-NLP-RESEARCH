from typing import Optional

from pydantic import BaseModel, Field, field_validator

class PredictRequest(BaseModel):
    # No upper bound: a user may paste a whole thesis or upload a long report, and a
    # cap here would reject it after the document had already been read and shown.
    text: str = Field(min_length=1)
    model: Optional[str] = None
    title: Optional[str] = None
    publish: bool = False

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text cannot be empty")
        return cleaned

class PredictResponse(BaseModel):
    prediction: str
    label: Optional[str] = None       # alias for prediction (frontend compat)
    confidence: Optional[float] = None
    score: Optional[float] = None     # alias for confidence (frontend compat)
    probabilities: dict[str, float]
    model: str
    history_saved: bool = True
    category: Optional[str] = None
    category_icon: Optional[str] = None
    prediction_id: Optional[str] = None


class PublishRequest(BaseModel):
    title: Optional[str] = None


class LinkAnalysisRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    model: Optional[str] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.lower().startswith(("http://", "https://")):
            raise ValueError("The address must start with http:// or https://")
        return cleaned


class LinkSegment(BaseModel):
    index: int
    words: int
    text: str
    # None when the paragraph was too short to score.
    verdict: Optional[str] = None
    scored: bool = False
    # None when the paragraph was skipped, or the model has no measured table.
    confidence: Optional[float] = None


class LinkAnalysisResponse(BaseModel):
    url: str
    title: Optional[str] = None
    word_count: int

    # Whole-article verdict: the one measured at 94.79% accuracy.
    prediction: str
    confidence: Optional[float] = None
    probabilities: dict[str, float]
    model: str

    category: Optional[str] = None
    category_icon: Optional[str] = None

    # Paragraph breakdown, so the result can be stated as a proportion.
    ai_percent: float
    human_percent: float
    ai_percent_by_words: float
    paragraphs_scored: int
    paragraphs_skipped: int
    ai_paragraphs: int
    human_paragraphs: int
    mean_paragraph_confidence: Optional[float] = None
    accuracy_measured: bool
    # True when the article was too short to split, so the proportion restates the
    # single verdict rather than counting paragraphs against each other.
    short_article: bool = False
    segments: list[LinkSegment]
    accuracy_note: str


class DocumentExtractResponse(BaseModel):
    """Text pulled from an uploaded Word or PDF file, ready to be classified."""

    filename: str
    file_type: str
    word_count: int
    char_count: int
    # Paragraph count is reported so the caller can tell a one-block document from a
    # structured one before deciding whether a per-paragraph breakdown is worth showing.
    paragraph_count: int
    text: str
