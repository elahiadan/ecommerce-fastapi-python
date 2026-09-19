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
| Database     | SQLite (dev) / Postgres        | Postgres via `DATABASE_URL` + bundled `psycopg2-binary` driver |
| Server       | Uvicorn                       | `uvicorn app.main:app --reload`        |
| Testing      | pytest + FastAPI TestClient  | local-only suite, in-memory SQLite (`StaticPool`), not shipped |
| Deploy       | Docker (python:3.12-slim)    | `docker build . && docker run`         |

## 📂 Project Structure

```
.
├── app/
│   ├── main.py               # FastAPI app, router registration, create_all
│   ├── config.py             # env-based settings (DATABASE_URL, JWT_SECRET_KEY, ...)
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
│       ├── auth.py           # /api/auth/register, /api/auth/login, /api/auth/me
│       ├── user.py           # /api/users (admin)
│       ├── category.py       # /api/categories
│       ├── product.py        # /api/products
│       ├── order.py          # /api/orders
│       └── review.py         # /api/reviews
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

# 3. Configure env — copy `.env.example` to `.env` and set JWT_SECRET_KEY (it
#    is REQUIRED — the app refuses to boot without it and rejects the known
#    dev default/placeholders). Generate one with:
#    python -c "import secrets; print(secrets.token_urlsafe(48))"
#    (Shell alternative:
#    export JWT_SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")")

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
docker run -p 8000:8000 -e JWT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" ecommerce-api
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

> All business routes are served under the `API_PREFIX` configured in `.env`
> (default `/api`), so endpoint URLs read `/api/auth/...`, `/api/products/...`
> and so on. The meta routes `GET /` and `GET /health` stay at the root so
> health checks and docs do not depend on the API prefix.

### Authentication / Users

| Method | Endpoint           | Auth  | Description                                      |
|--------|--------------------|-------|--------------------------------------------------|
| POST   | `/api/auth/register`   | –     | Create an account, returns the user (201)        |
| POST   | `/api/auth/login`      | –     | OAuth2 form (`username` + `password`), returns JWT |
| GET    | `/api/auth/me`         | user  | Current authenticated user                       |
| POST   | `/api/auth/change-password` | user | Change password (`current_password` + `new_password`), invalidates all existing tokens (204) |
| GET    | `/api/users/`          | admin | List all users                                   |
| GET    | `/api/users/{id}`      | user  | Own profile (admin: anyone)                      |

### Catalogue

| Method | Endpoint                    | Auth  | Description                                      |
|--------|-----------------------------|-------|--------------------------------------------------|
| GET    | `/api/categories/`               | –     | List categories                                   |
| POST   | `/api/categories/`               | admin | Create category                                   |
| GET    | `/api/categories/{id}`           | –     | Get category                                     |
| GET    | `/api/categories/{id}/products`  | –     | Products in a category                            |
| PATCH  | `/api/categories/{id}`           | admin | Update category                                   |
| DELETE | `/api/categories/{id}`           | admin | Delete category (409 if it has products)          |
| GET    | `/api/products/`                 | –     | List products (`category_id`, `search`, `min_price`, `max_price`, `skip`, `limit`) |
| POST   | `/api/products/`                 | admin | Create product                                    |
| GET    | `/api/products/{id}`             | –     | Product detail + `average_rating`, `review_count`, `reviews` |
| PATCH  | `/api/products/{id}`             | admin | Update product                                    |
| DELETE | `/api/products/{id}`             | admin | Delete product                                    |

### Orders & Reviews

| Method | Endpoint                  | Auth  | Description                                      |
|--------|---------------------------|-------|--------------------------------------------------|
| POST   | `/api/orders/`                | user  | Place an order (items with `product_id` + `quantity`) |
| GET    | `/api/orders/`                | user  | Own orders (admin: all orders)                   |
| GET    | `/api/orders/{id}`            | user  | Own order (admin: any; others get 404)           |
| PATCH  | `/api/orders/{id}/status`     | admin | Set status: `pending/paid/shipped/delivered/cancelled` |
| POST   | `/api/reviews/`               | user  | Review a product (`product_id`, `rating` 1–5, `comment?`) |
| GET    | `/api/reviews/`               | –     | List reviews (`product_id` filter)               |
| PATCH  | `/api/reviews/{id}`           | user  | Edit own review                                  |
| DELETE | `/api/reviews/{id}`           | user  | Delete own review (admin: any)                   |

Meta: `GET /` and `GET /health`.

## 💻 Example Requests

```bash
BASE=http://127.0.0.1:8000

# --- 1) Register & log in ------------------------------------------------
curl -s -X POST $BASE/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","username":"alice","full_name":"Alice","password":"password123"}'

TOKEN=$(curl -s -X POST $BASE/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'username=alice@example.com&password=password123' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# --- 2) Admin: create a category and a product ---------------------------
# (log in with the seeded admin instead for the admin actions)
ADMIN_TOKEN=$(curl -s -X POST $BASE/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'username=admin@example.com&password=admin123' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

CAT=$(curl -s -X POST $BASE/api/categories/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Electronics","description":"Gadgets"}')
CAT_ID=$(echo "$CAT" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -s -X POST $BASE/api/products/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d "{\"name\":\"Wireless Mouse\",\"price\":29.99,\"stock\":50,\"category_id\":$CAT_ID}"

# --- 3) User: place an order ---------------------------------------------
curl -s -X POST $BASE/api/orders/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"items":[{"product_id":1,"quantity":2}]}'

# --- 4) Review the product, then read its rating -------------------------
curl -s -X POST $BASE/api/reviews/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product_id":1,"rating":5,"comment":"Love it"}'

curl -s $BASE/api/products/1

# --- 5) Admin: update order status ---------------------------------------
curl -s -X PATCH $BASE/api/orders/1/status \
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

The app reads `DATABASE_URL` once at startup. A plain `postgresql://` URL uses
the bundled `psycopg2-binary` driver (already in `requirements.txt`), so
switching is just a matter of setting the variable:

```bash
export DATABASE_URL="postgresql://shop:secret@localhost:5432/shop"
export JWT_SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")"
uvicorn app.main:app
```

`create_all` runs at startup for any database by default (SQLite or Postgres),
so a fresh database works with zero setup. Disable it with
`AUTO_CREATE_TABLES=false` when you manage schema with
[Alembic](https://alembic.sqlalchemy.org/) migrations.

### Deploying to Vercel (serverless)

SQLite does not work there — the filesystem is read-only (except `/tmp`)
and ephemeral per instance — so the app refuses to boot with a SQLite URL
when the `VERCEL` env var is present. Set these in
**Project → Settings → Environment Variables**, then redeploy:

- `JWT_SECRET_KEY` — required (generate: `python -c "import secrets;
  print(secrets.token_urlsafe(48))"`)
- `DATABASE_URL` — a managed Postgres URL, e.g.
  `postgresql://user:pass@host:5432/shop`
  (`psycopg2-binary` is already in `requirements.txt`; on Vercel set
  `AUTO_CREATE_TABLES=true` to have the tables created at startup, or run
  migrations first)

Notes: empty-string env values are treated as unset (Vercel injects `""`
for blank variables); `ACCESS_TOKEN_EXPIRE_MINUTES` must be an integer ≥ 1.
The in-process auth rate limiter is per-instance on serverless — also enable
Vercel's platform rate limiting / firewall for the `/api/auth/*` routes.

## 🔐 Pinned Dependency Notes

- `bcrypt==4.0.1` is pinned deliberately. `passlib==1.7.4` reads bcrypt's
  `__about__` metadata module, removed in bcrypt ≥ 4.1, which raises an
  `AttributeError` at hashing time.
- `python-multipart` is required by FastAPI's `OAuth2PasswordRequestForm`.
- `email-validator` powers Pydantic's `EmailStr`.
- `psycopg2-binary` is pinned because `postgresql://` URLs (as documented in
  `.env.example`) resolve to the psycopg2 dialect in SQLAlchemy; the binary
  wheel bundles libpq so no system Postgres client is required.