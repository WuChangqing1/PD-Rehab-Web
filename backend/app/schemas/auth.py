"""Auth and staff schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "StaffUserRead"


class StaffUserRead(ORMModel):
    id: str
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime


TokenResponse.model_rebuild()
