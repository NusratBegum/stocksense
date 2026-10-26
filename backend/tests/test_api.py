from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from tests.conftest import signup

ORDERS = "/api/v1/orders"


def stock(client, auth, product_id):
    return next(p for p in client.get("/api/v1/products", headers=auth).json() if p["id"] == product_id)["stock_on_hand"]


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "database": "ok"}


def test_signup_and_login(client):
    signup(client)
    assert client.post("/api/v1/auth/signup", json={"email": "OWNER@example.com", "password": "x" * 8, "shop_name": "s"}).status_code == 409
    ok = client.post("/api/v1/auth/token", data={"username": "owner@example.com", "password": "correct-horse"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/api/v1/auth/token", data={"username": "owner@example.com", "password": "wrong-pass"})
    assert bad.status_code == 401


def test_requires_token(client):
    assert client.get("/api/v1/products").status_code == 401
    assert client.get("/api/v1/products", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_duplicate_sku_rejected(client, auth, product):
    r = client.post("/api/v1/products", json={"sku": "TOTE-01", "name": "x", "cost_price": "1", "sale_price": "2"}, headers=auth)
    assert r.status_code == 409


def test_order_reduces_stock_and_logs_movement(client, auth, product):
    r = client.post(ORDERS, json={"channel": "shopee", "items": [{"product_id": product["id"], "quantity": 3}]}, headers=auth)
    assert r.status_code == 201
    assert r.json()["total"] == "870.00"
    assert stock(client, auth, product["id"]) == 7
    moves = client.get("/api/v1/inventory/movements", headers=auth).json()
    assert [(m["change"], m["reason"]) for m in moves] == [(-3, "sale"), (10, "purchase")]


def test_order_rejects_overselling(client, auth, product):
    r = client.post(ORDERS, json={"channel": "lazada", "items": [{"product_id": product["id"], "quantity": 11}]}, headers=auth)
    assert r.status_code == 409
    assert r.json()["detail"]["items"][0]["available"] == 10
    assert stock(client, auth, product["id"]) == 10


def test_idempotency_key_prevents_double_sale(client, auth, product):
    body = {"channel": "line", "items": [{"product_id": product["id"], "quantity": 2}]}
    headers = {**auth, "Idempotency-Key": "line-msg-123"}
    first = client.post(ORDERS, json=body, headers=headers)
    retry = client.post(ORDERS, json=body, headers=headers)
    assert (first.status_code, retry.status_code) == (201, 200)
    assert first.json()["id"] == retry.json()["id"]
    assert stock(client, auth, product["id"]) == 8


def test_concurrent_orders_never_oversell(client, auth, product):
    body = {"channel": "facebook", "items": [{"product_id": product["id"], "quantity": 1}]}

    def place(_):
        return TestClient(client.app).post(ORDERS, json=body, headers=auth).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(place, range(16)))
    assert codes.count(201) == 10
    assert codes.count(409) == 6
    assert stock(client, auth, product["id"]) == 0


def test_cancel_restocks_and_blocks_invalid_moves(client, auth, product):
    order = client.post(ORDERS, json={"channel": "store", "items": [{"product_id": product["id"], "quantity": 4}]}, headers=auth).json()
    url = f"{ORDERS}/{order['id']}/status"
    assert client.patch(url, json={"status": "shipped"}, headers=auth).status_code == 409
    assert client.patch(url, json={"status": "cancelled"}, headers=auth).json()["status"] == "cancelled"
    assert stock(client, auth, product["id"]) == 10
    assert client.patch(url, json={"status": "paid"}, headers=auth).status_code == 409


def test_manual_movement_cannot_go_negative_or_fake_a_sale(client, auth, product):
    url = "/api/v1/inventory/movements"
    assert client.post(url, json={"product_id": product["id"], "change": -11, "reason": "adjustment"}, headers=auth).status_code == 409
    assert client.post(url, json={"product_id": product["id"], "change": -1, "reason": "sale"}, headers=auth).status_code == 422


def test_shops_are_isolated(client, auth, product):
    other = signup(client, "rival@example.com")
    assert client.get("/api/v1/products", headers=other).json() == []
    r = client.post(ORDERS, json={"channel": "shopee", "items": [{"product_id": product["id"], "quantity": 1}]}, headers=other)
    assert r.status_code == 404


def test_low_stock_filter(client, auth, product):
    client.post(ORDERS, json={"channel": "shopee", "items": [{"product_id": product["id"], "quantity": 7}]}, headers=auth)
    low = client.get("/api/v1/products?low_stock=true", headers=auth).json()
    assert [p["sku"] for p in low] == ["TOTE-01"] and low[0]["is_low_stock"]


def test_summary_counts_profit_by_channel_and_skips_cancelled(client, auth, product):
    pid = product["id"]
    client.post(ORDERS, json={"channel": "shopee", "items": [{"product_id": pid, "quantity": 2}]}, headers=auth)
    client.post(ORDERS, json={"channel": "lazada", "items": [{"product_id": pid, "quantity": 1}]}, headers=auth)
    cancelled = client.post(ORDERS, json={"channel": "line", "items": [{"product_id": pid, "quantity": 1}]}, headers=auth).json()
    client.patch(f"{ORDERS}/{cancelled['id']}/status", json={"status": "cancelled"}, headers=auth)

    s = client.get("/api/v1/analytics/summary?days=7", headers=auth).json()
    assert s["orders"] == 2
    assert s["revenue"] == "870.00"
    assert s["gross_profit"] == "510.00"
    assert {c["channel"]: c["revenue"] for c in s["by_channel"]} == {"shopee": "580.00", "lazada": "290.00"}
    assert len(s["daily"]) == 7 and s["daily"][-1]["revenue"] == "870.00"
