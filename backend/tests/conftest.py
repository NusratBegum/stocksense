import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@localhost:5433/stocksense_test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-use-0123456789")

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def signup(client: TestClient, email: str = "owner@example.com") -> dict[str, str]:
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse", "shop_name": "Bangkok Bags"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    return signup(client)


@pytest.fixture
def product(client: TestClient, auth: dict[str, str]) -> dict:
    r = client.post(
        "/api/v1/products",
        json={"sku": "TOTE-01", "name": "Canvas tote", "cost_price": "120.00", "sale_price": "290.00", "low_stock_threshold": 3},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/v1/inventory/movements",
        json={"product_id": r.json()["id"], "change": 10, "reason": "purchase"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    return client.get("/api/v1/products", headers=auth).json()[0]
