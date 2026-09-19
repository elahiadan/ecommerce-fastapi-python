"""Authentication endpoints: register, login (OAuth2 password flow), /me."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.rate_limit import rate_limit
from app.schemas.auth import Token
from app.schemas.user import PasswordChange, UserCreate, UserRead
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def _login_rate_key(request: Request) -> str:
    """Per-account bucket component. rate_limit() already prefixes every key
    with the client identity, so this returns only the account name: distinct
    accounts never share a bucket (a spray run cannot lock out unrelated
    users), while brute force against one account aggregates per account."""
    try:
        form = await request.form()
        username = form.get("username")
    except Exception:
        username = None
    account = (
        username.strip().lower()
        if isinstance(username, str) and username.strip()
        else "unknown"
    )
    return account


# Limits are env-configurable (LOGIN_/REGISTER_/CHANGE_PASSWORD_RATE_LIMIT_
# PER_MINUTE); the values below are only the fallbacks, read once at import.
_register_rate_limit = rate_limit(
    "auth:register", settings.register_rate_limit_per_minute, 60
)
_login_rate_limit = rate_limit(
    "auth:login",
    settings.login_rate_limit_per_minute,
    60,
    key=_login_rate_key,
)
_change_password_rate_limit = rate_limit(
    "auth:change-password", settings.change_password_rate_limit_per_minute, 60
)
# Pre-computed dummy hash so unknown-account logins still run a full bcrypt
# verify and respond in (roughly) the same time as a real one.
_DUMMY_HASH = hash_password("timing-equalization-dummy-password")


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _limited: None = Depends(_register_rate_limit),
) -> User:
    exists = db.query(User).filter(
        or_(User.email == payload.email, User.username == payload.username)
    ).first()
    if exists:
        # Single generic message on purpose: distinguishing email from username
        # would let anyone probe which accounts exist.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email or username already exists",
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
        # constraint. Same generic 409 keeps the enumeration surface closed.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email or username already exists",
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
    _limited: None = Depends(_login_rate_limit),
) -> Token:
    user = db.query(User).filter(
        or_(User.email == form_data.username, User.username == form_data.username)
    ).first()

    # Always run a real bcrypt verify (a dummy hash for unknown accounts) so
    # response timing does not reveal whether the account exists.
    password_ok = verify_password(
        form_data.password,
        user.hashed_password if user is not None else _DUMMY_HASH,
    )
    if user is None or not password_ok or not user.is_active:
        # One generic error for missing/invalid/deactivated accounts.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(
        access_token=create_access_token(
            subject=str(user.id), token_version=user.token_version
        )
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the currently authenticated user",
)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change your password (invalidates all existing tokens)",
)
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _limited: None = Depends(_change_password_rate_limit),
) -> None:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )
    current_user.hashed_password = hash_password(payload.new_password)
    # Bump the token version so every JWT issued before this change stops
    # validating in get_current_user (the `tv` claim check).
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit()