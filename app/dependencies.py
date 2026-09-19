"""Shared FastAPI dependencies: authentication and authorization."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the bearer token."""
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise _credentials_exception()
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise _credentials_exception()
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_exception()
    try:
        token_version = int(payload.get("tv", 0))
    except (TypeError, ValueError):
        raise _credentials_exception()
    if token_version != user.token_version:
        # The token was issued before the account's token_version was bumped
        # (e.g. after a password change) — treat it as invalid.
        raise _credentials_exception()
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that rejects non-admin users with a 403."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions: admin role required",
        )
    return current_user