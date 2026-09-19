"""FastAPI application entrypoint.

Run locally with:

    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.config import PROJECT_ROOT, settings
from app.routers import auth, category, order, product, review, user


def run_migrations() -> None:
    """Apply pending Alembic migrations to the configured database.

    Runs at every startup, so a first cold start on a fresh database creates
    the schema automatically; later boots are idempotent no-ops at head.

    The Alembic configuration is built in code (no ``alembic.ini``).
    """
    config = Config()
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "A small e-commerce backend built with FastAPI + SQLAlchemy: users, "
        "categories, products, orders (with atomic stock validation) and "
        "reviews. JWT auth with admin/user roles."
    ),
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# API_PREFIX from the environment (.env: API_PREFIX=/api). All routers are
# mounted beneath it, so the API lives at /api/auth/..., /api/products/... etc.
_api_prefix = settings.api_prefix.rstrip("/")
app.include_router(auth.router, prefix=_api_prefix)
app.include_router(user.router, prefix=_api_prefix)
app.include_router(category.router, prefix=_api_prefix)
app.include_router(product.router, prefix=_api_prefix)
app.include_router(order.router, prefix=_api_prefix)
app.include_router(review.router, prefix=_api_prefix)


@app.get("/", tags=["Meta"])
def root() -> dict:
    return {"message": "E-Commerce API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["Meta"])
def health_check() -> dict:
    return {"status": "ok"}