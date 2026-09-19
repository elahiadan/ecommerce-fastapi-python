"""Authentication endpoints: register, login (OAuth2 password flow), /me."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.rate_limit import rate_limit
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserRead
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])

_register_rate_limit = rate_limit("auth:register", 10, 60)
_login_rate_limit = rate_limit("auth:login", 20, 60)
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