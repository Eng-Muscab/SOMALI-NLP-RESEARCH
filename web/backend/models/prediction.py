from datetime import datetime

from pydantic import BaseModel, Field


class PredictionDocument(BaseModel):
    text: str
    prediction: str
    confidence: float | None = None
    probabilities: dict[str, float] = Field(default_factory=dict)
    model: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
