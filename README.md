# StockSense

**Inventory, orders and profit tracking for small online shops selling on several channels.**
One stock ledger across Shopee, Lazada, LINE, Facebook and a physical store, so a seller never sells stock they don't have and can see which channel actually makes money.

[![CI](https://github.com/NusratBegum/stocksense/actions/workflows/ci.yml/badge.svg)](https://github.com/NusratBegum/stocksense/actions/workflows/ci.yml)

**Live API docs:** https://stocksense-api.vercel.app/docs · **Demo login:** `demo@stocksense.dev` / `demo-shop-2026`

## What it does

- **One stock ledger.** Every change to stock is a row in `stock_movements` (purchase, adjustment, return, sale, cancellation), and a database check stops `stock_on_hand` from going below zero.
- **No overselling.** Creating an order locks the product rows (`SELECT ... FOR UPDATE`, in id order to avoid deadlocks) inside one transaction. A test fires 16 parallel orders at 10 units in stock: exactly 10 succeed.
- **Safe retries.** Send an `Idempotency-Key` header and a retried request returns the first order instead of selling the stock twice.
- **Order lifecycle.** pending → paid → shipped, or cancelled, which puts the stock back.
- **Sales summary.** Revenue, gross profit and order count per channel and per day (Bangkok time) in SQL, skipping cancelled orders. Prices and costs are copied onto each order line, so later price changes don't rewrite history.
- **Accounts.** Each owner gets one shop. OAuth2 password flow with JWT access tokens and bcrypt-hashed passwords; every query is scoped to the caller's shop.

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI, Pydantic v2, SQLAlchemy 2.0, OAuth2 + JWT, bcrypt |
| Database | PostgreSQL (Neon in production) |
| Tests | pytest against a real PostgreSQL, GitHub Actions |
| Hosting | Vercel |

## API

| Method | Path | What it does |
|---|---|---|
| POST | `/api/v1/auth/signup` | Create an owner account and shop |
| POST | `/api/v1/auth/token` | Log in, get a JWT |
| GET / POST | `/api/v1/products` | List (optionally only low stock) or add products |
| PATCH | `/api/v1/products/{id}` | Update name, prices or low-stock threshold |
| GET / POST | `/api/v1/inventory/movements` | Stock history, or record a purchase, adjustment or return |
| GET / POST | `/api/v1/orders` | List orders, or create one (honours `Idempotency-Key`) |
| PATCH | `/api/v1/orders/{id}/status` | Move an order through its lifecycle |
| GET | `/api/v1/analytics/summary?days=30` | Revenue, gross profit and orders by channel and day |

## Run it locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/stocksense
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
python -m app.seed              # tables + a demo shop with 60 days of orders
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

Tests need an empty PostgreSQL database:

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/stocksense_test JWT_SECRET=test python -m pytest
```

## Project layout

```
backend/
  app/
    main.py          FastAPI app, CORS, health check
    models.py        SQLAlchemy models and constraints
    schemas.py       Pydantic request and response models
    security.py      bcrypt, JWT, current-shop dependency
    routers/         auth, products, inventory, orders, analytics
    seed.py          demo shop with 60 days of orders
  tests/test_api.py  13 API tests on PostgreSQL
```

## Author

Built by [Nusrat Begum](https://nusratbegum.dev).
