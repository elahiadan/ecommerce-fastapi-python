"""Review request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.user import UserRead


class ReviewCreate(BaseModel):
    product_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewUpdate(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("rating")
    @classmethod
    def _rating_not_null(cls, value: int | None) -> int | None:
        # `rating` is a NOT NULL column with a 1-5 CHECK; an explicit null is a
        # client bug -> 422 rather than a DB 500.
        if value is None:
            raise ValueError("rating cannot be null")
        return value


class ReviewRead(ORMModel):
    id: int
    user_id: int
    product_id: int
    rating: int
    comment: str | None
    created_at: datetime
    user: UserRead | None = None