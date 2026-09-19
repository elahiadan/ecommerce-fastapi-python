"""Security helpers: password hashing and JWT creation/decoding.

bcrypt is pinned to a version that is compatible with passlib 1.7.4:
newer bcrypt releases dropped the ``__about__`` metadata module that passlib
reads, which causes a spurious ``AttributeError`` at runtime. See requirements.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, token_version: int = 0) -> str:
    """Encode a JWT containing the subject (user id), a token version and an
    expiry. ``tv`` lets us invalidate every previously issued token (e.g. after
    a password change) by bumping ``User.token_version``."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "tv": token_version,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT. Returns the claims dict, or None if invalid."""
    try:
        return jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except JWTError:
        return None