"""Order endpoints.

Key business rule: when placing an order every line item is validated against
available stock BEFORE any quantity is decremented. If any line exceeds stock
the whole request is rejected and nothing is mutated (no partial decrements).
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post(
    "/",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Place an order (any authenticated user)",
)
def create_order(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Order:
    # Aggregate requested quantities per product so duplicate line items for
    # the same product cannot bypass the stock check.
    requested: dict[int, int] = {}
    for item in payload.items:
        requested[item.product_id] = requested.get(item.product_id, 0) + item.quantity

    if not requested:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    product_ids = list(requested.keys())
    # FOR UPDATE locks the rows on Postgres (ignored by SQLite) so concurrent
    # check-then-decrement stays safe; everything happens in one transaction.
    products = (
        db.query(Product)
        .filter(Product.id.in_(product_ids))
        .with_for_update()
        .all()
    )
    product_map: dict[int, Product] = {p.id: p for p in products}

    # --- Phase 1: validate every line BEFORE touching any data ------------
    for product_id, quantity in requested.items():
        product = product_map.get(product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product with id {product_id} does not exist",
            )
        if quantity > product.stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for '{product.name}': "
                    f"requested {quantity}, only {product.stock} available"
                ),
            )

    # --- Phase 2: create order + items, decrement stock, all in one commit ----
    order = Order(user_id=current_user.id)
    db.add(order)
    db.flush()  # obtain order.id

    total = Decimal("0.00")
    for product_id, quantity in requested.items():
        product = product_map[product_id]
        product.stock -= quantity
        total += Decimal(quantity) * product.price
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product_id,
                quantity=quantity,
                price_at_purchase=product.price,
            )
        )

    order.total_amount = total
    db.commit()
    db.refresh(order)
    return order


@router.get(
    "/",
    response_model=list[OrderRead],
    summary="List orders (own orders, or all orders for admins)",
)
def list_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    query = db.query(Order)
    if not current_user.is_admin:
        query = query.filter(Order.user_id == current_user.id)
    return query.offset(skip).limit(limit).all()


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    summary="Get a single order (owner or admin)",
)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Order:
    order = db.get(Order, order_id)
    if order is None or (order.user_id != current_user.id and not current_user.is_admin):
        # 404 (rather than 403) so we don't leak whether an order exists.
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch(
    "/{order_id}/status",
    response_model=OrderRead,
    summary="Update an order's status (admin only)",
)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order