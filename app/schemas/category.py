"""Category request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _name_not_null(cls, value: str | None) -> str | None:
        # `name` is a NOT NULL unique column; explicit null -> 422, not a DB 500.
        if value is None:
            raise ValueError("name cannot be null")
        return value


class CategoryRead(ORMModel):
    id: int
    name: str
    description: str | None
    created_at: datetime