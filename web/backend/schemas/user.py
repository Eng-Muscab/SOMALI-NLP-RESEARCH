from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from ..models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserOut(BaseModel):
    id: Optional[str] = None
    email: EmailStr
    name: str = ""
    role: str = UserRole.VIEWER


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# ── Admin schemas ──────────────────────────────────────────────────────────────

class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = ""
    role: UserRole = UserRole.VIEWER
    daily_prediction_limit: int = Field(default=20, ge=-1)
    monthly_prediction_limit: int = Field(default=200, ge=-1)
    max_text_length: int = Field(default=2000, ge=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    daily_prediction_limit: Optional[int] = Field(default=None, ge=-1)
    monthly_prediction_limit: Optional[int] = Field(default=None, ge=-1)
    max_text_length: Optional[int] = Field(default=None, ge=100)


class AdminUserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: str
    last_login: Optional[str] = None
    daily_prediction_count: int
    monthly_prediction_count: int
    daily_prediction_limit: int
    monthly_prediction_limit: int
    max_text_length: int


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


# ── Activity log schema ───────────────────────────────────────────────────────

class ActivityLogOut(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_name: str
    action: str
    category: str
    details: dict
    status: str
    created_at: str
