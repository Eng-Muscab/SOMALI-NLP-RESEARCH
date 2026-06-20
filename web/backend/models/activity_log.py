from datetime import datetime

from pydantic import BaseModel, Field


class ActivityLogDocument(BaseModel):
    user_id: str
    user_email: str
    user_name: str = ""
    action: str          # login, logout, predict, user_created, user_updated, role_changed, etc.
    category: str        # auth, prediction, admin, system
    details: dict = Field(default_factory=dict)
    ip_address: str | None = None
    status: str = "success"  # success | failure
    created_at: datetime = Field(default_factory=datetime.utcnow)
