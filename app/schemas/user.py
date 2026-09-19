"""User request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel


def _check_password_bytes(value: str) -> str:
    # bcrypt only uses the first 72 bytes; reject longer passwords instead
    # of silently ignoring the tail.
    if len(value.encode("utf-8")) > 72:
        raise ValueError("password must be at most 72 bytes")
    return value


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _password_max_bytes(cls, value: str) -> str:
        return _check_password_bytes(value)


class PasswordChange(BaseModel):
    """Authenticated password change. Success bumps the account's
    token_version, invalidating every previously issued JWT."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _new_password_max_bytes(cls, value: str) -> str:
        return _check_password_bytes(value)


class UserRead(ORMModel):
    id: int
    email: EmailStr
    username: str
    full_name: str | None
    is_admin: bool
    is_active: bool
    created_at: datetime