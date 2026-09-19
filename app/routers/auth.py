"""Authentication endpoints: register, login (OAuth2 password flow), /me."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserRead
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    exists = db.query(User).filter(
        or_(User.email == payload.email, User.username == payload.username)
    ).first()
    if exists:
        if exists.email == payload.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken",
        )

    user = User(
        email=payload.email,
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Unique-column backstop for the concurrent-signup race: the
        # pre-checks above both pass, then the second INSERT trips the unique
        # constraint. Re-query so the friendly 409/username message still wins.
        db.rollback()
        existing = (
            db.query(User)
            .filter(
                or_(
                    User.email == payload.email,
                    User.username == payload.username,
                )
            )
            .first()
        )
        if existing is not None and existing.email == payload.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken",
        )
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Exchange email/username + password for a JWT",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    user = db.query(User).filter(
        or_(User.email == form_data.username, User.username == form_data.username)
    ).first()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )

    return Token(access_token=create_access_token(subject=str(user.id)))


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the currently authenticated user",
)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user