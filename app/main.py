"""FastAPI application entrypoint.

Run locally with:

    alembic upgrade head
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.routers import auth, category, order, product, review, user

app = FastAPI(
    title=settings.app_name,
    description=(
        "A small e-commerce backend built with FastAPI + SQLAlchemy: users, "
        "categories, products, orders (with atomic stock validation) and "
        "reviews. JWT auth with admin/user roles."
    ),
    version=settings.app_version,
    debug=settings.debug,
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
    database = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        database = "unavailable"
    return {"status": "ok", "database": database}