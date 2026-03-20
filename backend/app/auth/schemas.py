"""Auth request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(None, max_length=100)


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefresh(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    display_name: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}
