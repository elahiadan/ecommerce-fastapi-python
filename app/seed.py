"""One-command demo seed: creates an admin user plus sample catalogue.

Run with:

    python -m app.seed

Credentials created (unless they already exist):
    admin@example.com / admin123

Safe to re-run: existing users/categories are left untouched.
"""

from decimal import Decimal

from app.database import SessionLocal
from app.main import run_migrations
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.security import hash_password

DEMO_ADMIN_EMAIL = "admin@example.com"
DEMO_ADMIN_PASSWORD = "admin123"
DEMO_ADMIN_USERNAME = "admin"

DEMO_CATEGORIES = [
    ("Electronics", "Gadgets, devices and accessories."),
    ("Books", "Printed and digital reading material."),
    ("Clothing", "Tops, bottoms and outerwear."),
]

DEMO_PRODUCTS = [
    ("Wireless Mouse", "Ergonomic 2.4GHz wireless mouse.", Decimal("19.99"), 50, "Electronics"),
    ("Mechanical Keyboard", "Hot-swappable 75% mechanical keyboard.", Decimal("89.99"), 30, "Electronics"),
    ("USB-C Charger", "65W GaN wall charger.", Decimal("29.99"), 120, "Electronics"),
    ("Project Hail Mary", "Sci-fi bestseller paperback edition.", Decimal("12.50"), 80, "Books"),
    ("Clean Code", "Robert C. Martin's classic.", Decimal("49.99"), 40, "Books"),
    ("Cotton T-Shirt", "Plain heavyweight cotton tee.", Decimal("15.00"), 200, "Clothing"),
]


def seed() -> None:
    run_migrations()  # tables come from Alembic migrations, not create_all

    with SessionLocal() as db:
        admin = db.query(User).filter(User.email == DEMO_ADMIN_EMAIL).first()
        if admin is None:
            admin = User(
                email=DEMO_ADMIN_EMAIL,
                username=DEMO_ADMIN_USERNAME,
                full_name="Demo Administrator",
                is_admin=True,
                hashed_password=hash_password(DEMO_ADMIN_PASSWORD),
            )
            db.add(admin)
            print(f"Created admin user: {DEMO_ADMIN_EMAIL} / {DEMO_ADMIN_PASSWORD}")

        category_by_name: dict[str, Category] = {}
        for name, description in DEMO_CATEGORIES:
            category = db.query(Category).filter(Category.name == name).first()
            if category is None:
                category = Category(name=name, description=description)
                db.add(category)
                print(f"Created category: {name}")
            category_by_name[name] = category

        db.flush()  # assign category ids

        for name, description, price, stock, category_name in DEMO_PRODUCTS:
            exists = db.query(Product).filter(Product.name == name).first()
            if exists is None:
                db.add(
                    Product(
                        name=name,
                        description=description,
                        price=price,
                        stock=stock,
                        image_url=None,
                        category_id=category_by_name[category_name].id,
                    )
                )
                print(f"Created product: {name}")

        db.commit()

    print("Seeding complete.")


if __name__ == "__main__":
    seed()