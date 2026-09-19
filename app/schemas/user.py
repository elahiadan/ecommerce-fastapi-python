"""User request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    is_active: bool | None = None


class UserRead(ORMModel):
    id: int
    email: EmailStr
    username: str
    full_name: str | None
    is_admin: bool
    is_active: bool
    created_at: datetime