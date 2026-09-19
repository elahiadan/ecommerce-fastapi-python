"""Application configuration.

Reads settings from environment variables (optionally loaded from a .env file).
``JWT_SECRET_KEY`` is required: the app refuses to boot without it so a
deployment can never silently fall back to a known, forgeable JWT signing key.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

_DEV_SECRET = "dev-secret-key-change-me-in-production"
# Placeholder shipped in .env.example — accepted nowhere, so a copy of the
# example without an edited secret fails closed instead of signing with it.
_PLACEHOLDER_SECRETS = {_DEV_SECRET, "CHANGE_ME"}

# Absolute path of the project root (the directory containing app/).
# Relative SQLite file paths are resolved against this, not the process
# working directory, so the dev database always lands in the same place no
# matter where uvicorn/pytest is launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

_SQLITE_DEFAULT = "sqlite:///./ecommerce.db"


def _resolve_database_url(url: str) -> str:
    """Resolve a relative SQLite file URL against PROJECT_ROOT.

    sqlite:///./ecommerce.db and sqlite:///sub/dev.db are project-relative.
    Absolute paths (sqlite:////tmp/x.db), :memory:, and non-SQLite URLs are
    returned unchanged.
    """
    if not url.startswith("sqlite:"):
        return url
    if ":memory:" in url:
        return url
    parts = urlsplit(url)
    if parts.path.startswith("//"):
        return url  # already absolute (four-slash form)
    relative = (parts.netloc + parts.path).lstrip("/")
    # urlsplit puts the "." host of sqlite:///./f.db into netloc.
    if relative.startswith("./"):
        relative = relative[2:]
    if not relative or relative == ".":
        return url
    absolute = (PROJECT_ROOT / relative).as_posix()
    return f"sqlite:///{absolute}"


def _default_auto_create_tables() -> bool:
    explicit = _getenv("AUTO_CREATE_TABLES", "")
    if explicit:
        return explicit.lower() in ("1", "true", "yes")
    # Default to creating tables on startup for every database (SQLite dev and
    # managed Postgres/Neon alike), so a fresh database "just works" with no
    # .env changes. Serverless (Vercel) is the exception: static-filesystem
    # and multi-instance concerns make runtime DDL inappropriate, so there it
    # stays opt-in via AUTO_CREATE_TABLES=1/true.
    if os.getenv("VERCEL"):
        return False
    return True


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
        default_factory=lambda: _getenv("DATABASE_URL", _SQLITE_DEFAULT)
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
    # Zero-setup behaviour: tables are created on startup for any database
    # (SQLite and Postgres/Neon) unless EXPLICITLY disabled with
    # AUTO_CREATE_TABLES=0/false, or when running on Vercel (serverless),
    # where DDL at runtime is disabled unless AUTO_CREATE_TABLES=1/true.
    # Production teams that manage schema with Alembic can disable it here.
    auto_create_tables: bool = field(
        default_factory=_default_auto_create_tables
    )

    def __post_init__(self) -> None:
        # Frozen dataclass: normalize the URL once, at construction.
        object.__setattr__(
            self, "database_url", _resolve_database_url(self.database_url)
        )
        if not self.secret_key or self.secret_key in _PLACEHOLDER_SECRETS:
            raise RuntimeError(
                "JWT_SECRET_KEY (or SECRET_KEY) is required and must not be "
                "a known default or placeholder. Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if os.getenv("VERCEL") and self.database_url.startswith("sqlite"):
            raise RuntimeError(
                "SQLite cannot be used on Vercel (read-only, ephemeral "
                "filesystem). Set DATABASE_URL to a managed Postgres "
                "database, e.g. "
                "DATABASE_URL=postgresql://user:pass@host:5432/shop"
            )


settings = Settings()