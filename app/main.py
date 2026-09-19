"""FastAPI application entrypoint.

Run locally with:

    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.database import Base, engine
from app.models import Category, Order, OrderItem, Product, Review, User  # noqa: F401
from app.routers import auth, category, order, product, review, user

# Create tables on startup (fine for local dev; use Alembic for migrations
# when running against a shared Postgres database).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="E-Commerce API",
    description=(
        "A small e-commerce backend built with FastAPI + SQLAlchemy: users, "
        "categories, products, orders (with atomic stock validation) and "
        "reviews. JWT auth with admin/user roles."
    ),
    version="1.0.0",
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