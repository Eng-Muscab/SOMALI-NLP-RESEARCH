from datetime import datetime

from pydantic import BaseModel, Field


class DatasetDocument(BaseModel):
    filename: str
    path: str
    size: int
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
