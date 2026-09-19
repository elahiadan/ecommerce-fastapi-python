"""Product endpoints. Reads are public; writes are admin-only."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import require_admin
from app.models.category import Category
from app.models.order import OrderItem
from app.models.product import Product
from app.models.review import Review
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductDetail,
    ProductRead,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.post(
    "/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product (admin only)",
)
def create_product(
    payload: ProductCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Product:
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=400, detail="Category does not exist")

    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get(
    "/",
    response_model=list[ProductRead],
    summary="List products (filtering + pagination)",
)
def list_products(
    db: Session = Depends(get_db),
    category_id: int | None = Query(default=None),
    search: str | None = Query(default=None, description="Match product name"),
    min_price: float | None = Query(default=None),
    max_price: float | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Product]:
    query = db.query(Product)
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    # Deterministic ordering so pagination never duplicates or skips rows.
    return query.order_by(Product.id).offset(skip).limit(limit).all()


@router.get(
    "/{product_id}",
    response_model=ProductDetail,
    summary="Get a product with its average rating and review count",
)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductDetail:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    avg_rating, review_count = (
        db.query(func.avg(Review.rating), func.count(Review.id))
        .filter(Review.product_id == product_id)
        .one()
    )

    # Only the most recent reviews are serialized — returning every review
    # would make the public detail response grow without bound. The count
    # above still reflects the full set.
    recent_reviews = (
        db.query(Review)
        .options(selectinload(Review.user))
        .filter(Review.product_id == product_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
        .limit(5)
        .all()
    )

    return ProductDetail(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price,
        stock=product.stock,
        image_url=product.image_url,
        category_id=product.category_id,
        created_at=product.created_at,
        reviews=recent_reviews,
        average_rating=round(float(avg_rating), 2) if avg_rating is not None else None,
        review_count=int(review_count),
    )


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    summary="Update a product (admin only)",
)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = payload.model_dump(exclude_unset=True)
    if "category_id" in updates:
        if db.get(Category, updates["category_id"]) is None:
            raise HTTPException(status_code=400, detail="Category does not exist")

    for field, value in updates.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product (admin only)",
)
def delete_product(
    product_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if db.query(OrderItem.id).filter(OrderItem.product_id == product_id).first():
        # Historical line items must survive, so an ordered product cannot be
        # deleted (a raw FK IntegrityError would otherwise surface as a 500).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a product that has been ordered",
        )
    db.delete(product)
    db.commit()