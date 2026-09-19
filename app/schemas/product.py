"""Product request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import Money, ORMModel
from app.schemas.review import ReviewRead


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    price: Money = Field(gt=0)
    stock: int = Field(default=0, ge=0)
    image_url: str | None = Field(default=None, max_length=500)
    category_id: int


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    price: Money | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=500)
    category_id: int | None = None

    @field_validator("name", "price", "stock", "category_id")
    @classmethod
    def _reject_null(cls, value, info):
        # These map to NOT NULL columns. `exclude_unset=True` already drops
        # omitted fields, so an explicit null here is a client bug -> 422,
        # never a 500 from the DB.
        if value is None:
            raise ValueError(f"{info.field_name} cannot be null")
        return value


class ProductRead(ORMModel):
    id: int
    name: str
    description: str | None
    price: Money
    stock: int
    image_url: str | None
    category_id: int
    created_at: datetime


class ProductDetail(ProductRead):
    """Product plus computed review aggregates for the detail view.

    ``reviews`` holds only the 5 most recent reviews (the response must stay
    bounded); ``review_count`` always reflects the full review set.
    """

    average_rating: float | None
    review_count: int
    reviews: list[ReviewRead] = Field(
        default_factory=list,
        description=(
            "The 5 most recent reviews (newest first). review_count reflects "
            "every review for the product."
        ),
    )