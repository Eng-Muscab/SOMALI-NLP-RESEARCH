from datetime import datetime

from pydantic import BaseModel, Field


class PredictionDocument(BaseModel):
    text: str
    prediction: str
    confidence: float | None = None
    probabilities: dict[str, float] = Field(default_factory=dict)
    model: str | None = None
    category: str | None = None
    category_icon: str | None = None
    user_id: str | None = None
    user_email: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    title: str | None = None
    is_published: bool = False
    author_name: str | None = None
    published_at: datetime | None = None
