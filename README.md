# StockSense

**Inventory, orders and profit tracking for small online shops selling on several channels.**
One stock ledger across Shopee, Lazada, LINE, Facebook and a physical store, so a seller never sells stock they don't have and can see which channel actually makes money.

[![CI](https://github.com/NusratBegum/stocksense/actions/workflows/ci.yml/badge.svg)](https://github.com/NusratBegum/stocksense/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![React 18](https://img.shields.io/badge/React_18-20232A?logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)

**[Open the live dashboard](https://stocksense-demo-mauve.vercel.app)** · [API docs (Swagger)](https://stocksense-api-nine.vercel.app/docs) · Demo login: `demo@stocksense.dev` / `demo-shop-2026`

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/dashboard-dark.png">
  <img alt="StockSense dashboard: revenue, profit and order KPIs, a daily revenue chart, sales by channel, a new-order form and the product list with low-stock badges" src="docs/dashboard-light.png">
</picture>

### Try it in 30 seconds

1. Open the [live dashboard](https://stocksense-demo-mauve.vercel.app) and press **Sign in** (the demo account is filled in).
2. In **New order**, pick a product marked **Low** and ask for more than is in stock. The API refuses with `409 Not enough stock`.
3. Order an amount that fits. Stock drops, the order appears under **Recent orders**, and revenue updates.
4. Press **+20** on a product to record a purchase, or cancel an order to put its stock back.

## How it works

```mermaid
flowchart LR
  UI["React + TypeScript dashboard<br/>(Vite, Vercel)"] -- "JWT, JSON" --> API["FastAPI<br/>(Vercel Python function)"]
  API -- "SQLAlchemy 2.0<br/>SELECT ... FOR UPDATE" --> DB[("PostgreSQL<br/>(Neon)")]
  CI["GitHub Actions"] -- "pytest on Postgres 16" --> API
```

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
| Dashboard | React 18, TypeScript, Vite, plain CSS with light and dark themes, SVG chart |
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

In a second terminal, start the dashboard:

```bash
cd frontend
npm ci
VITE_API_URL=http://localhost:8000 npm run dev   # http://localhost:5173
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
frontend/
  src/
    App.tsx          dashboard: KPIs, chart, channels, orders, products
    RevenueChart.tsx SVG bar chart with hover tooltips
    api.ts           typed API client (JWT, Idempotency-Key)
docs/                screenshots
```

## Author

Built by [Nusrat Begum](https://nusratbegum.dev).
