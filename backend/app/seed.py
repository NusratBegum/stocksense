"""Create the tables and a demo shop with 60 days of orders.

Run once against an empty database:  python -m app.seed
"""
import os
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text

from app.db import Base, SessionLocal, engine
from app.models import (
    Channel,
    MovementReason,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    Shop,
    StockMovement,
    User,
)
from app.security import hash_password

DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@stocksense.dev")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo-shop-2026")

CATALOG = [
    ("TOTE-CNV", "Canvas tote bag", "120", "290"),
    ("TEE-WHT-M", "Cotton tee, white, M", "95", "250"),
    ("TEE-BLK-L", "Cotton tee, black, L", "95", "250"),
    ("CAP-NVY", "Twill cap, navy", "80", "220"),
    ("MUG-CER", "Ceramic mug", "60", "180"),
    ("BOTL-STL", "Steel water bottle", "150", "390"),
    ("NOTE-A5", "A5 dot notebook", "45", "140"),
    ("PIN-SET", "Enamel pin set", "35", "120"),
    ("SOCK-STR", "Striped socks", "40", "129"),
    ("PHN-CASE", "Phone case, clear", "55", "199"),
    ("KEY-CHN", "Elephant keychain", "20", "79"),
    ("SCRF-SLK", "Silk scarf", "260", "690"),
]
# Rough share of orders per channel for a small Thai online shop.
CHANNEL_WEIGHTS = {Channel.shopee: 40, Channel.lazada: 25, Channel.line: 15, Channel.facebook: 12, Channel.store: 8}


def seed(days: int = 60) -> None:
    Base.metadata.create_all(engine)
    rng = random.Random(2026)
    with SessionLocal() as db:
        # Serverless cold starts can run this at the same time; one seeds, the rest wait and skip.
        db.execute(text("SELECT pg_advisory_xact_lock(20261102)"))
        if db.scalar(select(User).where(User.email == DEMO_EMAIL)):
            print("Demo shop already exists")
            return
        user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        user.shop = Shop(name="Siam Street Goods")
        db.add(user)
        db.flush()
        shop_id = user.shop.id

        start = datetime.now(timezone.utc) - timedelta(days=days)
        products = []
        for sku, name, cost, price in CATALOG:
            p = Product(
                shop_id=shop_id, sku=sku, name=name, cost_price=Decimal(cost), sale_price=Decimal(price),
                stock_on_hand=0, low_stock_threshold=5,
            )
            db.add(p)
            products.append(p)
        db.flush()

        def restock(p: Product, qty: int, when: datetime) -> None:
            p.stock_on_hand += qty
            db.add(StockMovement(product_id=p.id, change=qty, reason=MovementReason.purchase, created_at=when))

        for p in products:
            restock(p, rng.randint(40, 80), start)

        channels, weights = zip(*CHANNEL_WEIGHTS.items())
        for day in range(days):
            for _ in range(rng.randint(3, 9) + (3 if (start + timedelta(days=day)).weekday() >= 5 else 0)):
                when = start + timedelta(days=day, minutes=rng.randint(8 * 60, 22 * 60))
                picks = rng.sample(products, k=rng.choice([1, 1, 1, 2, 2, 3]))
                order = Order(shop_id=shop_id, channel=rng.choices(channels, weights)[0], created_at=when)
                for p in picks:
                    qty = rng.choice([1, 1, 1, 2, 3])
                    if p.stock_on_hand < qty:
                        restock(p, rng.randint(30, 60), when - timedelta(minutes=5))
                    p.stock_on_hand -= qty
                    order.items.append(OrderItem(product_id=p.id, quantity=qty, unit_price=p.sale_price, unit_cost=p.cost_price))
                    db.add(StockMovement(product_id=p.id, change=-qty, reason=MovementReason.sale, order=order, created_at=when))
                age = days - day
                if rng.random() < 0.05:
                    order.status = OrderStatus.cancelled
                    for item in order.items:
                        p = next(x for x in products if x.id == item.product_id)
                        p.stock_on_hand += item.quantity
                        db.add(StockMovement(product_id=p.id, change=item.quantity, reason=MovementReason.cancellation, order=order, created_at=when + timedelta(hours=1)))
                else:
                    order.status = OrderStatus.shipped if age > 2 else rng.choice([OrderStatus.pending, OrderStatus.paid])
                db.add(order)

        # Leave a few items low so the low-stock view has something to show.
        for p in products[-3:]:
            if p.stock_on_hand > 4:
                change = -(p.stock_on_hand - rng.randint(1, 4))
                p.stock_on_hand += change
                db.add(StockMovement(product_id=p.id, change=change, reason=MovementReason.adjustment, note="Stock count"))
        db.commit()
        print(f"Seeded {DEMO_EMAIL} with {len(products)} products")


if __name__ == "__main__":
    seed()
