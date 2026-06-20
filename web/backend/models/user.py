from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    ANALYST = "analyst"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


ROLE_LIMITS: dict[str, dict] = {
    UserRole.SUPER_ADMIN: {"daily": -1, "monthly": -1, "max_text": 10000},
    UserRole.ADMIN:       {"daily": -1, "monthly": -1, "max_text": 10000},
    UserRole.ANALYST:     {"daily": 200, "monthly": 3000, "max_text": 5000},
    UserRole.RESEARCHER:  {"daily": 500, "monthly": 10000, "max_text": 5000},
    UserRole.VIEWER:      {"daily": 20, "monthly": 200, "max_text": 2000},
}


class UserDocument(BaseModel):
    email: EmailStr
    password: str
    name: str = ""
    role: str = UserRole.VIEWER
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: datetime | None = None
    daily_prediction_count: int = 0
    monthly_prediction_count: int = 0
    daily_prediction_limit: int = 20
    monthly_prediction_limit: int = 200
    max_text_length: int = 2000
    last_count_reset: str = ""  # YYYY-MM-DD
    last_month_reset: str = ""  # YYYY-MM
