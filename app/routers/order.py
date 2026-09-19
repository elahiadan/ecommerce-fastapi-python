"""Order endpoints.

Key business rule: when placing an order every line item is validated against
available stock BEFORE any quantity is decremented. If any line exceeds stock
the whole request is rejected and nothing is mutated (no partial decrements).

Decrements are performed with an atomic conditional ``UPDATE ... WHERE
stock >= quantity``, so a concurrent order can never oversell the same stock
between the check and the write.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate

router = APIRouter(prefix="/orders", tags=["Orders"])

# Valid lifecycle transitions. DELIVERED and CANCELLED are terminal: a
# cancelled order's stock is restored exactly once, so it must never leave
# that state again (which would allow double-restocking).
_ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


def _get_order_with_items(
    db: Session, order_id: int, *, for_update: bool = False
) -> Order | None:
    """Load an order with its line items and products eager-loaded so response
    serialization never triggers an N+1 of lazy queries. Pass for_update=True
    when the caller is about to change the row, so concurrent status updates
    stay serialized."""
    query = (
        db.query(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .filter(Order.id == order_id)
    )
    if for_update:
        query = query.with_for_update()
    return query.first()


@router.post(
    "/",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Place an order (any authenticated user)",
)
def create_order(
    payload: OrderCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", max_length=128
    ),
) -> Order:
    idempotency_key = (idempotency_key or "").strip() or None

    # A replayed checkout (double-click, client retry) reuses the original
    # order instead of placing a duplicate and decrementing stock twice.
    if idempotency_key:
        existing = (
            db.query(Order)
            .filter(
                Order.user_id == current_user.id,
                Order.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return _get_order_with_items(db, existing.id)

    # Aggregate requested quantities per product so duplicate line items for
    # the same product cannot bypass the stock check.
    requested: dict[int, int] = {}
    for item in payload.items:
        requested[item.product_id] = requested.get(item.product_id, 0) + item.quantity

    if not requested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order must contain at least one item",
        )

    product_ids = list(requested.keys())
    # FOR UPDATE locks the rows on Postgres so concurrent check-then-decrement
    # stays serialized; everything happens in one transaction.
    products = (
        db.query(Product)
        .filter(Product.id.in_(product_ids))
        .with_for_update()
        .all()
    )
    product_map: dict[int, Product] = {p.id: p for p in products}

    # --- Phase 1: friendly validation before touching any data -------------
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

    # --- Phase 2: create order + items, decrement stock, all in one commit ---
    order = Order(user_id=current_user.id, idempotency_key=idempotency_key)
    db.add(order)
    db.flush()  # obtain order.id

    total = Decimal("0.00")
    for product_id, quantity in requested.items():
        product = product_map[product_id]
        # Atomic conditional decrement: if the row no longer has enough stock
        # (concurrent order), zero rows match and we reject — no partial writes.
        result = db.execute(
            sa_update(Product)
            .where(Product.id == product_id, Product.stock >= quantity)
            .values(stock=Product.stock - quantity)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for '{product.name}': requested {quantity}",
            )
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
    try:
        db.commit()
    except IntegrityError:
        # Two cases: (1) a concurrent request already placed the same checkout
        # (unique (user_id, idempotency_key) constraint) -> replay that order;
        # (2) a product was deleted concurrently while we held its rows ->
        # friendly 409, never a raw driver 500. Either way nothing was written.
        db.rollback()
        if idempotency_key:
            existing = (
                db.query(Order)
                .filter(
                    Order.user_id == current_user.id,
                    Order.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing is not None:
                response.status_code = status.HTTP_200_OK
                return _get_order_with_items(db, existing.id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Order could not be placed because a product changed "
                "concurrently. Please retry."
            ),
        )
    return _get_order_with_items(db, order.id)


@router.get(
    "/",
    response_model=list[OrderRead],
    summary="List orders (own orders, or all orders for admins)",
)
def list_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    query = db.query(Order).options(
        selectinload(Order.items).selectinload(OrderItem.product)
    )
    if not current_user.is_admin:
        query = query.filter(Order.user_id == current_user.id)
    # Deterministic ordering so pagination never duplicates or skips rows.
    return query.order_by(Order.id.desc()).offset(skip).limit(limit).all()


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
    order = _get_order_with_items(db, order_id)
    if order is None or (order.user_id != current_user.id and not current_user.is_admin):
        # 404 (rather than 403) so we don't leak whether an order exists.
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch(
    "/{order_id}/status",
    response_model=OrderRead,
    summary="Update an order's status (admin only, lifecycle-validated)",
)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Order:
    # Lock the row: without this, two concurrent cancels both read a
    # cancellable status, both pass the transition check, and stock is
    # restored twice (CANCELLED-is-terminal is otherwise only a Python check).
    order = _get_order_with_items(db, order_id, for_update=True)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    new_status = payload.status
    if new_status == order.status:
        return order  # idempotent no-op

    allowed = _ALLOWED_TRANSITIONS[order.status]
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot change order status from '{order.status.value}' to "
                f"'{new_status.value}'. Allowed transitions: "
                f"{', '.join(sorted(s.value for s in allowed)) or 'none'}"
            ),
        )

    if new_status == OrderStatus.CANCELLED:
        # Restock every line atomically. CANCELLED is terminal, so this runs
        # exactly once (a later status change is rejected above).
        for item in order.items:
            result = db.execute(
                sa_update(Product)
                .where(Product.id == item.product_id)
                .values(stock=Product.stock + item.quantity)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Cannot cancel order: product {item.product_id} is no "
                        "longer available"
                    ),
                )

    # Serialize the transition in the database: the UPDATE only matches a row
    # that is still in the status we read, so a concurrent request that already
    # moved this order wins and this one is rejected with a clean 409 instead
    # of restocking twice.
    transition = db.execute(
        sa_update(Order)
        .where(Order.id == order.id, Order.status == order.status)
        .values(status=new_status)
        .execution_options(synchronize_session=False)
    )
    if transition.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order status changed concurrently; please retry",
        )

    db.commit()
    return _get_order_with_items(db, order.id)