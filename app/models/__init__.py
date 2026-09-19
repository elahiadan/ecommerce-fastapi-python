"""Model re-exports.

Importing this module registers every model on ``Base.metadata`` so that
``create_all`` / ``drop_all`` know about all tables.
"""

from app.models.category import Category
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.review import Review
from app.models.user import User

__all__ = [
    "Category",
    "Order",
    "OrderItem",
    "OrderStatus",
    "Product",
    "Review",
    "User",
]