# 🛒 E-Commerce REST API

A small, production-minded e-commerce backend built with **FastAPI** and
**SQLAlchemy** — designed as a portfolio/interview project that demonstrates
clean layering, authentication & authorization, transactional business logic,
and a real test suite.

## ✨ Highlights

- **JWT authentication** (OAuth2 password flow) with **bcrypt** password hashing, admin/user roles
- **Catalogue**: categories + products (admin-managed), public reads with filtering/pagination
- **Orders** with atomic stock validation — *all* line items are validated
  before *any* quantity is decremented, so a failing line never leaves partial stock changes
- **Reviews**: one review per user per product (DB constraint + friendly 409),
  computed average rating & count on the product detail endpoint
- **Role-based permissions**: 403 for non-admins on write routes; users only
  see their own orders; admins moderate reviews and update order status
- Switcheable database: SQLite out of the box, Postgres via a `DATABASE_URL` env var
- ✔ **Local pytest suite** exercising auth, permissions, stock validation, and review rules (kept out of this repository)

## 🛠 Tech Stack

| Layer        | Tool                          | Note                                   |
|--------------|-------------------------------|----------------------------------------|
| Framework    | FastAPI `0.115.0`            | Pydantic v2 validation                 |
| ORM          | SQLAlchemy `2.0.35`          | `Mapped`/`mapped_column` typing        |
| Validation   | Pydantic `2.9.2`             | request/response schemas               |
| Auth         | `python-jose` + `passlib`    | HS256 JWT + bcrypt hashing             |
| Database     | SQLite (dev)                  | swap to Postgres via `DATABASE_URL`    |
| Server       | Uvicorn                       | `uvicorn app.main:app --reload`        |
| Testing      | pytest + FastAPI TestClient  | local-only suite, in-memory SQLite (`StaticPool`), not shipped |
| Deploy       | Docker (python:3.12-slim)    | `docker build . && docker run`         |

## 📂 Project Structure

```
.
├── app/
│   ├── main.py               # FastAPI app, router registration, create_all
│   ├── config.py             # env-based settings (DATABASE_URL, SECRET_KEY, ...)
│   ├── database.py           # engine / session / Base / get_db
│   ├── security.py           # bcrypt hashing + JWT encode/decode
│   ├── dependencies.py       # get_current_user, require_admin
│   ├── seed.py               # demo data seeder (python -m app.seed)
│   ├── models/               # SQLAlchemy ORM models, one file per entity
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── product.py
│   │   ├── order.py          # Order, OrderItem, OrderStatus
│   │   └── review.py
│   ├── schemas/              # Pydantic v2 schemas, one file per entity
│   │   ├── common.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── product.py
│   │   ├── order.py
│   │   └── review.py
│   └── routers/              # API routers, one file per entity
│       ├── auth.py           # /auth/register, /auth/login, /auth/me
│       ├── user.py           # /users (admin)
│       ├── category.py       # /categories
│       ├── product.py        # /products
│       ├── order.py          # /orders
│       └── review.py         # /reviews
├── requirements.txt          # pinned versions
├── Dockerfile
└── .env.example
```

## 🏃 Setup & Run

```bash
# 1. Create and activate a virtual environment
python3.12 -m venv venv
source venv/bin/activate

# 2. Install pinned dependencies
pip install -r requirements.txt

# 3. Set a JWT signing key (REQUIRED — the app refuses to boot without it and
#    rejects the known dev default)
export SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")"

# 4. (Optional) seed a demo admin + catalogue
python -m app.seed
#    creates: admin@example.com / admin123

# 5. Run the server
uvicorn app.main:app --reload
```

Open the interactive docs at **http://127.0.0.1:8000/docs**.

### Run with Docker

```bash
docker build -t ecommerce-api .
docker run -p 8000:8000 -e SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" ecommerce-api
```

### Run the tests

The pytest suite is intentionally kept **out of this repository**. If you have a
local checkout containing `tests/`, just run:

```bash
pytest            # or: pytest -v
```

Right after cloning, `pytest` will find no test cases — that is expected.

## 🧪 Business Rules

The rules below are exercised by a **local pytest suite that is not included in
this repository** (see *Run the tests*):

- Duplicate signup email/username rejected with a single generic `409`
- Non-admin write routes return `403`
- Order succeeds and stock is decremented atomically
- Insufficient stock → `400`, nothing decremented
- One failing line ⇒ *no* partial decrement on other lines
- Invalid order-status transitions → `409`; cancelling restores stock exactly once
- Users only see their own orders; admins see all + set status
- Duplicate review → `409`; one review per user/product
- Average rating + review count on product detail
- Users delete only own reviews; admins moderate any

## 🔌 API Endpoints

### Authentication / Users

| Method | Endpoint           | Auth  | Description                                      |
|--------|--------------------|-------|--------------------------------------------------|
| POST   | `/auth/register`   | –     | Create an account, returns the user (201)        |
| POST   | `/auth/login`      | –     | OAuth2 form (`username` + `password`), returns JWT |
| GET    | `/auth/me`         | user  | Current authenticated user                       |
| GET    | `/users/`          | admin | List all users                                   |
| GET    | `/users/{id}`      | user  | Own profile (admin: anyone)                      |

### Catalogue

| Method | Endpoint                    | Auth  | Description                                      |
|--------|-----------------------------|-------|--------------------------------------------------|
| GET    | `/categories/`               | –     | List categories                                   |
| POST   | `/categories/`               | admin | Create category                                   |
| GET    | `/categories/{id}`           | –     | Get category                                     |
| GET    | `/categories/{id}/products`  | –     | Products in a category                            |
| PATCH  | `/categories/{id}`           | admin | Update category                                   |
| DELETE | `/categories/{id}`           | admin | Delete category (409 if it has products)          |
| GET    | `/products/`                 | –     | List products (`category_id`, `search`, `min_price`, `max_price`, `skip`, `limit`) |
| POST   | `/products/`                 | admin | Create product                                    |
| GET    | `/products/{id}`             | –     | Product detail + `average_rating`, `review_count`, `reviews` |
| PATCH  | `/products/{id}`             | admin | Update product                                    |
| DELETE | `/products/{id}`             | admin | Delete product                                    |

### Orders & Reviews

| Method | Endpoint                  | Auth  | Description                                      |
|--------|---------------------------|-------|--------------------------------------------------|
| POST   | `/orders/`                | user  | Place an order (items with `product_id` + `quantity`) |
| GET    | `/orders/`                | user  | Own orders (admin: all orders)                   |
| GET    | `/orders/{id}`            | user  | Own order (admin: any; others get 404)           |
| PATCH  | `/orders/{id}/status`     | admin | Set status: `pending/paid/shipped/delivered/cancelled` |
| POST   | `/reviews/`               | user  | Review a product (`product_id`, `rating` 1–5, `comment?`) |
| GET    | `/reviews/`               | –     | List reviews (`product_id` filter)               |
| PATCH  | `/reviews/{id}`           | user  | Edit own review                                  |
| DELETE | `/reviews/{id}`           | user  | Delete own review (admin: any)                   |

Meta: `GET /` and `GET /health`.

## 💻 Example Requests

```bash
BASE=http://127.0.0.1:8000

# --- 1) Register & log in ------------------------------------------------
curl -s -X POST $BASE/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","username":"alice","full_name":"Alice","password":"password123"}'

TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'username=alice@example.com&password=password123' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# --- 2) Admin: create a category and a product ---------------------------
# (log in with the seeded admin instead for the admin actions)
ADMIN_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'username=admin@example.com&password=admin123' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

CAT=$(curl -s -X POST $BASE/categories/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Electronics","description":"Gadgets"}')
CAT_ID=$(echo "$CAT" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -s -X POST $BASE/products/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"Wireless Mouse\",\"price\":29.99,\"stock\":50,\"category_id\":$CAT_ID}"

# --- 3) User: place an order ---------------------------------------------
curl -s -X POST $BASE/orders/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"items":[{"product_id":1,"quantity":2}]}'

# --- 4) Review the product, then read its rating -------------------------
curl -s -X POST $BASE/reviews/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id":1,"rating":5,"comment":"Love it"}'

curl -s $BASE/products/1

# --- 5) Admin: update order status ---------------------------------------
curl -s -X PATCH $BASE/orders/1/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"shipped"}'
```

## 🔑 Important Business Rules

- **Atomic order placement.** Every line item's quantity is aggregated per
  product and validated against stock *before* anything is mutated. If any
  line is invalid, the whole request returns `400` and **no** product is
  decremented. Writes happen in a single transaction; `SELECT … FOR UPDATE`
  locks rows on Postgres for safe concurrent checkout (SQLite ignores it).
- **Price snapshotting.** `OrderItem.price_at_purchase` records the price at
  order time; later price changes never rewrite historical orders.
- **One review per user per product** is enforced as a DB
  `UNIQUE(user_id, product_id)` constraint *and* surfaced as a friendly `409`
  in the API.
- **Ownership.** Users see only their own orders (others get `404`). Users may
  update/delete only their own reviews; admins can delete any review.

## 🗄️ Swapping SQLite → Postgres

The app reads `DATABASE_URL` once at startup:

```bash
export DATABASE_URL="postgresql+psycopg://shop:secret@localhost:5432/shop"
export SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")"
uvicorn app.main:app
```

`create_all` is used for local dev. For real deployments add
[Alembic](https://alembic.sqlalchemy.org/) migrations.

## 🔐 Pinned Dependency Notes

- `bcrypt==4.0.1` is pinned deliberately. `passlib==1.7.4` reads bcrypt's
  `__about__` metadata module, removed in bcrypt ≥ 4.1, which raises an
  `AttributeError` at hashing time.
- `python-multipart` is required by FastAPI's `OAuth2PasswordRequestForm`.
- `email-validator` powers Pydantic's `EmailStr`.