"""User admin endpoints: list and inspect users."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/",
    response_model=list[UserRead],
    summary="List all users (admin only)",
)
def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> list[User]:
    return db.query(User).order_by(User.id).offset(skip).limit(limit).all()


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get a single user (admin only, or yourself)",
)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    # Users may only fetch their own profile; admins may fetch anyone's.
    if user is None or (user_id != current_user.id and not current_user.is_admin):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user