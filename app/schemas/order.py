"""Order request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.order import OrderStatus
from app.schemas.common import Money, ORMModel
from app.schemas.product import ProductRead


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderItemRead(ORMModel):
    id: int
    product_id: int
    quantity: int
    price_at_purchase: Money
    product: ProductRead | None = None


class OrderRead(ORMModel):
    id: int
    user_id: int
    status: OrderStatus
    total_amount: Money
    created_at: datetime
    items: list[OrderItemRead] = []


class OrderStatusUpdate(BaseModel):
    status: OrderStatus