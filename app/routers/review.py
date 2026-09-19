"""Review endpoints.

Rules:
- Any authenticated user can create a review (one per user/product).
- A user may delete/edit only their own review.
- An admin may delete any review (moderation).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.product import Product
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewRead, ReviewUpdate

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post(
    "/",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Review a product (once per user/product, any authenticated user)",
)
def create_review(
    payload: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Review:
    if db.get(Product, payload.product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (
        db.query(Review)
        .filter(
            Review.user_id == current_user.id,
            Review.product_id == payload.product_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reviewed this product",
        )

    review = Review(
        user_id=current_user.id,
        product_id=payload.product_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        # Unique constraint backstop (e.g. concurrent duplicate submissions).
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reviewed this product",
        )
    db.refresh(review)
    return review


@router.get(
    "/",
    response_model=list[ReviewRead],
    summary="List reviews (optionally filtered by product)",
)
def list_reviews(
    db: Session = Depends(get_db),
    product_id: int | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Review]:
    query = db.query(Review)
    if product_id is not None:
        query = query.filter(Review.product_id == product_id)
    return query.order_by(Review.created_at.desc()).offset(skip).limit(limit).all()


@router.patch(
    "/{review_id}",
    response_model=ReviewRead,
    summary="Update your own review",
)
def update_review(
    review_id: int,
    payload: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Review:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own reviews",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(review, field, value)
    db.commit()
    db.refresh(review)
    return review


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a review (own review, or any review for admins)",
)
def delete_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own reviews",
        )
    db.delete(review)
    db.commit()