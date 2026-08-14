from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    ANALYST = "analyst"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


# -1 means unlimited. Every role is unlimited on every axis: this is a research
# platform used by the project team and their supervisor, and a per-day cap only ever
# interrupted their own testing. The one limit users still meet is the *minimum* text
# length (MIN_TEXT_LENGTH in predict_controller.py), which exists because a classifier
# given four words has nothing to work with.
ROLE_LIMITS: dict[str, dict] = {
    UserRole.SUPER_ADMIN: {"daily": -1, "monthly": -1, "max_text": -1},
    UserRole.ADMIN:       {"daily": -1, "monthly": -1, "max_text": -1},
    UserRole.ANALYST:     {"daily": -1, "monthly": -1, "max_text": -1},
    UserRole.RESEARCHER:  {"daily": -1, "monthly": -1, "max_text": -1},
    UserRole.VIEWER:      {"daily": -1, "monthly": -1, "max_text": -1},
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
    # -1 is the unlimited sentinel throughout. This is a research platform whose
    # users are the project team and their supervisor; a per-day cap only ever
    # interrupted their own testing.
    daily_prediction_limit: int = -1
    monthly_prediction_limit: int = -1
    max_text_length: int = -1
    last_count_reset: str = ""  # YYYY-MM-DD
    last_month_reset: str = ""  # YYYY-MM
