"""Category endpoints. Reads are public; writes are admin-only."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.schemas.product import ProductRead

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post(
    "/",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category (admin only)",
)
def create_category(
    payload: CategoryCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Category:
    if db.query(Category).filter(Category.name == payload.name).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists",
        )
    category = Category(**payload.model_dump())
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent create with the same name: unique constraint backstop.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists",
        )
    db.refresh(category)
    return category


@router.get(
    "/",
    response_model=list[CategoryRead],
    summary="List all categories",
)
def list_categories(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> list[Category]:
    return db.query(Category).order_by(Category.id).offset(skip).limit(limit).all()


@router.get(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Get a single category",
)
def get_category(category_id: int, db: Session = Depends(get_db)) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.get(
    "/{category_id}/products",
    response_model=list[ProductRead],
    summary="List products belonging to a category",
)
def list_category_products(
    category_id: int,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> list[Product]:
    if db.get(Category, category_id) is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return (
        db.query(Product)
        .filter(Product.category_id == category_id)
        .order_by(Product.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Update a category (admin only)",
)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] != category.name:
        if db.query(Category).filter(Category.name == updates["name"]).first():
            raise HTTPException(
                status_code=409, detail="A category with this name already exists"
            )

    for field, value in updates.items():
        setattr(category, field, value)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent rename to an existing name: unique constraint backstop.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists",
        )
    db.refresh(category)
    return category


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category (admin only)",
)
def delete_category(
    category_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.products:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a category that still contains products",
        )
    db.delete(category)
    db.commit()