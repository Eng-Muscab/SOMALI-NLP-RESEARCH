from typing import Optional

from pydantic import BaseModel, Field, field_validator

class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    model: Optional[str] = None

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
