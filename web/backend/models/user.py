from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserDocument(BaseModel):
    email: EmailStr
    password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
