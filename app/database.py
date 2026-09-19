"""Database engine and session setup.

Uses SQLite by default (zero external setup). Swap to Postgres in production by
setting DATABASE_URL, e.g.:

    export DATABASE_URL=postgresql://user:pass@localhost:5432/shop
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _engine_options(database_url: str) -> dict:
    # Managed/hosted Postgres (e.g. Neon) closes idle pooled connections; the
    # pool re-validates a connection with a cheap SELECT 1 before use so a
    # stale pooled connection never 500s the next request. SQLite keeps its
    # current behaviour untouched.
    if database_url.startswith("sqlite"):
        return {}
    return {"pool_pre_ping": True}


engine = create_engine(
    settings.database_url,
    connect_args=_connect_args(settings.database_url),
    **_engine_options(settings.database_url),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()