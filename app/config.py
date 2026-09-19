"""Application configuration.

Reads settings from environment variables (optionally loaded from a .env file).
``DATABASE_URL`` and ``JWT_SECRET_KEY`` are required: the app refuses to boot
without them so a deployment can never silently fall back to an unconfigured
database or a known, forgeable JWT signing key.
"""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

_DEV_SECRET = "dev-secret-key-change-me-in-production"
# Placeholder shipped in .env.example — accepted nowhere, so a copy of the
# example without an edited secret fails closed instead of signing with it.
_PLACEHOLDER_SECRETS = {_DEV_SECRET, "CHANGE_ME"}


def _getenv(name: str, default: str) -> str:
    """Read an env var, treating unset AND empty string as missing.

    Platforms such as Vercel inject empty strings for unset variables, so a
    plain os.getenv(name, default) would hand the empty string to the caller.
    """
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _getenv_optional(name: str) -> str | None:
    """Read an env var as None when unset or empty (empty == unset)."""
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return value


def _secret_key_value() -> str:
    # Canonical name is JWT_SECRET_KEY (as documented in .env.example);
    # SECRET_KEY is still honoured as a fallback so existing deployments are
    # not broken. Precedence keeps one source of truth when both are set.
    return (
        _getenv_optional("JWT_SECRET_KEY")
        or _getenv_optional("SECRET_KEY")
        or ""
    )


def _algorithm_value() -> str:
    return (
        _getenv_optional("JWT_ALGORITHM")
        or _getenv_optional("ALGORITHM")
        or "HS256"
    )


def _getenv_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = _getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(
            f"{name} must be an integer, got {raw!r}. "
            f"Unset it to use the default ({default})."
        )
    if minimum is not None and value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}, got {value}.")
    return value


@dataclass(frozen=True)
class Settings:
    # Application metadata (documented in .env.example).
    app_name: str = field(default_factory=lambda: _getenv("APP_NAME", "E-Commerce API"))
    app_version: str = field(default_factory=lambda: _getenv("APP_VERSION", "1.0.0"))
    debug: bool = field(
        default_factory=lambda: _getenv("DEBUG", "false").lower()
        in ("1", "true", "yes")
    )
    environment: str = field(
        default_factory=lambda: _getenv("ENVIRONMENT", "development")
    )
    api_prefix: str = field(default_factory=lambda: _getenv("API_PREFIX", "/api"))

    database_url: str = field(
        default_factory=lambda: _getenv("DATABASE_URL", "")
    )
    secret_key: str = field(default_factory=_secret_key_value)
    algorithm: str = field(default_factory=_algorithm_value)
    access_token_expire_minutes: int = field(
        default_factory=lambda: _getenv_int(
            "ACCESS_TOKEN_EXPIRE_MINUTES", 60, minimum=1
        )
    )
    # Auth rate limits (requests per client per 60 s window). Defaults match
    # the values documented in .env.example.
    login_rate_limit_per_minute: int = field(
        default_factory=lambda: _getenv_int(
            "LOGIN_RATE_LIMIT_PER_MINUTE", 10, minimum=1
        )
    )
    register_rate_limit_per_minute: int = field(
        default_factory=lambda: _getenv_int(
            "REGISTER_RATE_LIMIT_PER_MINUTE", 20, minimum=1
        )
    )
    change_password_rate_limit_per_minute: int = field(
        default_factory=lambda: _getenv_int(
            "CHANGE_PASSWORD_RATE_LIMIT_PER_MINUTE", 10, minimum=1
        )
    )

    def __post_init__(self) -> None:
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL is required. Copy .env.example to .env and set "
                "it to a PostgreSQL URL, e.g. "
                "DATABASE_URL=postgresql://user:pass@host:5432/shop"
            )
        db_scheme = urlsplit(self.database_url).scheme
        if (
            db_scheme not in ("postgres", "postgresql")
            and not db_scheme.startswith(("postgres+", "postgresql+"))
        ):
            raise RuntimeError(
                "Only Postgres is supported; SQLite and other databases are "
                "not. Set DATABASE_URL to a postgresql:// URL."
            )
        if not self.secret_key or self.secret_key in _PLACEHOLDER_SECRETS:
            raise RuntimeError(
                "JWT_SECRET_KEY (or SECRET_KEY) is required and must not be "
                "a known default or placeholder. Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )


settings = Settings()