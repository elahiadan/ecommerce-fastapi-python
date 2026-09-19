"""FastAPI application entrypoint.

Run locally with:

    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import Base, engine
from app.models import Category, Order, OrderItem, Product, Review, User  # noqa: F401
from app.routers import auth, category, order, product, review, user


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are created at startup — never at import — so a cold start on a
    # read-only/ephemeral filesystem (or a misconfigured DATABASE_URL) fails
    # here with a clear error instead of "could not import app/main.py".
    # Only enabled for local SQLite dev (or explicit AUTO_CREATE_TABLES=1);
    # shared databases must be migrated with Alembic.
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
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

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(category.router)
app.include_router(product.router)
app.include_router(order.router)
app.include_router(review.router)


@app.get("/", tags=["Meta"])
def root() -> dict:
    return {"message": "E-Commerce API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["Meta"])
def health_check() -> dict:
    return {"status": "ok"}