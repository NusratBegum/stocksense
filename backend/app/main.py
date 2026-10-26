from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import CORS_ORIGINS
from app.db import engine
from app.routers import analytics, auth, inventory, orders, products

app = FastAPI(
    title="StockSense API",
    version="1.0.0",
    description="Inventory and multi-channel order tracking for small online shops.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (auth.router, products.router, inventory.router, orders.router, analytics.router):
    app.include_router(router, prefix="/api/v1")


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
