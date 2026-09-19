"""Application configuration.

Reads settings from environment variables (optionally loaded from a .env file).
``SECRET_KEY`` is required: the app refuses to boot without it so a deployment
can never silently fall back to a known, forgeable JWT signing key.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

_DEV_SECRET = "dev-secret-key-change-me-in-production"


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///./ecommerce.db"
        )
    )
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", ""))
    algorithm: str = field(
        default_factory=lambda: os.getenv("ALGORITHM", "HS256")
    )
    access_token_expire_minutes: int = field(
        default_factory=lambda: int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )
    )

    def __post_init__(self) -> None:
        if not self.secret_key or self.secret_key == _DEV_SECRET:
            raise RuntimeError(
                "SECRET_KEY is required and must not be the known default. "
                "Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )


settings = Settings()