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
- PostgreSQL-only via a `DATABASE_URL` env var; schema managed by Alembic migrations (`alembic upgrade head`)
- ✔ **Local pytest suite** exercising auth, permissions, stock validation, and review rules (kept out of this repository)

## 🛠 Tech Stack

| Layer        | Tool                          | Note                                   |
|--------------|-------------------------------|----------------------------------------|
| Framework    | FastAPI `0.115.0`            | Pydantic v2 validation                 |
| ORM          | SQLAlchemy `2.0.35`          | `Mapped`/`mapped_column` typing        |
| Validation   | Pydantic `2.9.2`             | request/response schemas               |
| Auth         | `python-jose` + `passlib`    | HS256 JWT + bcrypt hashing             |
| Database     | PostgreSQL                 | Postgres via `DATABASE_URL` + bundled `psycopg2-binary` driver |
| Migrations   | Alembic `1.13.4`           | `alembic upgrade head` via CLI, `docker compose up`, or `docker compose --profile local up` |
| Server       | Uvicorn                       | `uvicorn app.main:app --reload`        |
| Testing      | pytest + FastAPI TestClient  | local-only suite against Postgres (isolated schema), not shipped |
| Deploy       | Docker + docker-compose   | `docker compose --profile local up` (app + Postgres) |

## 📂 Project Structure

```
.
├── app/
│   ├── main.py               # FastAPI app, router registration, health check
│   ├── config.py             # env-based settings (DATABASE_URL, JWT_SECRET_KEY, ...)
│   ├── database.py           # engine / session / Base / get_db
│   ├── security.py           # bcrypt hashing + JWT encode/decode
│   ├── dependencies.py       # get_current_user, require_admin
│   ├── seed.py               # demo data seeder (alembic upgrade head first, then python -m app.seed)
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
├── alembic/
│   ├── env.py                # reads sqlalchemy.url from Settings (app/config.py)
│   ├── script.py.mako        # template for new migrations
│   └── versions/             # e.g. 0001_create_ecommerce_tables.py
├── alembic.ini               # Alembic CLI config (script_location = alembic)
├── requirements.txt          # pinned versions
├── Dockerfile
├── docker-compose.yml        # api + optional local Postgres (--profile local)
├── .dockerignore
└── .env.example
```

## 🏃 Setup & Run

```bash
# 1. Create and activate a virtual environment
python3.12 -m venv venv
source venv/bin/activate

# 2. Install pinned dependencies
pip install -r requirements.txt

# 3. Configure env — copy `.env.example` to `.env`. `DATABASE_URL` (a
#    PostgreSQL URL) and `JWT_SECRET_KEY` are REQUIRED — the app refuses to
#    boot without them and rejects the known dev default/placeholders.
#    Generate a secret with:
#    python -c "import secrets; print(secrets.token_urlsafe(48))"
#    (Shell alternative:
#    export JWT_SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")")

# 3b. Apply migrations
#     alembic upgrade head
#     (the container retries automatically against a not-yet-ready database)

# 4. (Optional) seed a demo admin + catalogue
python -m app.seed
#    creates: admin@example.com / admin123

# 5. Run the server
uvicorn app.main:app --reload
```

Open the interactive docs at **http://127.0.0.1:8000/docs**.

### Run with Docker

```bash
docker compose up                # app only (uses DATABASE_URL from .env, e.g. Neon)
docker compose --profile local up   # app + local PostgreSQL (drops into the db service)
```

Or build and run manually:

```bash
alembic upgrade head             # run migrations first
docker build -t ecommerce-api .
docker run -p 8000:8000 -e JWT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" ecommerce-api
```

### Run the tests

The pytest suite is intentionally kept **out of this repository**. If you have a
local checkout containing `tests/`, run:

```bash
pytest            # or: pytest -v
```

Right after cloning, `pytest` will find no test cases — that is expected.
Tests run against the PostgreSQL server in `DATABASE_URL` and isolate each test
inside a throwaway schema, so they never touch real tables.

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
| GET    | `/api/products/{id}`             | –     | Product detail + `average_rating`, `review_count`, `reviews` (5 most recent) |
| PATCH  | `/api/products/{id}`             | admin | Update product                                    |
| DELETE | `/api/products/{id}`             | admin | Delete product                                    |

### Orders & Reviews

| Method | Endpoint                  | Auth  | Description                                      |
|--------|---------------------------|-------|--------------------------------------------------|
| POST   | `/api/orders/`                | user  | Place an order (items with `product_id` + `quantity`). Pass an `Idempotency-Key` header to make replays safe (double-click/retry reuse the original order) |
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
  locks rows on Postgres for safe concurrent checkout.
- **Idempotent checkout.** Send the same `Idempotency-Key` header with an
  order to make a retried or double-submitted request reuse the original
  order (200) instead of placing a duplicate or charging again. Keys are
  scoped per user; a unique `(user_id, idempotency_key)` constraint backstops
  concurrent double-submits.
- **Price snapshotting.** `OrderItem.price_at_purchase` records the price at
  order time; later price changes never rewrite historical orders.
- **One review per user per product** is enforced as a DB
  `UNIQUE(user_id, product_id)` constraint *and* surfaced as a friendly `409`
  in the API. Product detail returns the product's `average_rating`,
  `review_count` (the full set) and the **5 most recent** reviews.
- **Ownership.** Users see only their own orders (others get `404`). Users may
  update/delete only their own reviews; admins can delete any review.
- **Timezone-aware timestamps.** All `created_at` values are stored and served
  as `timestamptz` (UTC), so clients always receive an explicit offset.

## 🗄️ Database & Migrations

The app is Postgres-only: `DATABASE_URL` is read once at startup. A plain
`postgresql://` URL uses the bundled `psycopg2-binary` driver (already in
`requirements.txt`).

```bash
export DATABASE_URL="postgresql://shop:secret@localhost:5432/shop"
export JWT_SECRET_KEY="$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")"
alembic upgrade head             # create/update the schema
uvicorn app.main:app
```

Schema changes live in `alembic/versions/` and are applied with the Alembic CLI
(`alembic.ini` points `script_location` at `alembic/`, and `alembic/env.py`
reads the URL from the app settings). When running `docker compose`, the api
container retries `alembic upgrade head` until the database is ready, then
starts uvicorn. To autogenerate a new revision after editing a model:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Use `--profile local` to bring up a bundled Postgres 16 alongside the app; the
container credentials are `ecom`/`ecom`/`ecom` on `localhost:5432`, so point
`DATABASE_URL` at `postgresql://ecom:ecom@localhost:5432/ecom` for that mode.

The initial migration `0001_create_ecommerce_tables.py` creates the whole
schema on a fresh database.

### Deploying to Vercel (serverless)

Set these in **Project → Settings → Environment Variables**, then redeploy:

- `JWT_SECRET_KEY` — required (generate: `python -c "import secrets;
  print(secrets.token_urlsafe(48))"`)
- `DATABASE_URL` — a managed Postgres URL, e.g.
  `postgresql://user:pass@host:5432/shop`
  (`psycopg2-binary` is already in `requirements.txt`). Run `alembic upgrade
  head` against the database (from any machine, once) so the tables exist
  before the first cold start; the serverless runtime does not run migrations.

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