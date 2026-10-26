from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Channel, MovementReason, Order, OrderItem, OrderStatus, Product, Shop, StockMovement
from app.schemas import OrderIn, OrderOut, StatusUpdate
from app.security import current_shop

router = APIRouter(prefix="/orders", tags=["orders"])

ALLOWED = {
    OrderStatus.pending: {OrderStatus.paid, OrderStatus.cancelled},
    OrderStatus.paid: {OrderStatus.shipped, OrderStatus.cancelled},
    OrderStatus.shipped: set(),
    OrderStatus.cancelled: set(),
}


def _find_order(db: Session, shop: Shop, order_id: int) -> Order:
    order = db.scalar(
        select(Order).where(Order.id == order_id, Order.shop_id == shop.id).options(selectinload(Order.items))
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Order {order_id} not found")
    return order


def _by_key(db: Session, shop: Shop, key: str) -> Order | None:
    return db.scalar(
        select(Order)
        .where(Order.shop_id == shop.id, Order.idempotency_key == key)
        .options(selectinload(Order.items))
    )


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    body: OrderIn,
    response: Response,
    idempotency_key: str | None = Header(default=None, max_length=100),
    shop: Shop = Depends(current_shop),
    db: Session = Depends(get_db),
) -> Order:
    # A retried request (same key) gets the first order back instead of selling the stock twice.
    if idempotency_key and (existing := _by_key(db, shop, idempotency_key)):
        response.status_code = status.HTTP_200_OK
        return existing

    quantities: dict[int, int] = {}
    for item in body.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity

    # Lock rows in id order so two orders for the same products can't deadlock or oversell.
    products = {
        p.id: p
        for p in db.scalars(
            select(Product)
            .where(Product.shop_id == shop.id, Product.id.in_(quantities))
            .order_by(Product.id)
            .with_for_update()
        )
    }
    missing = sorted(set(quantities) - set(products))
    if missing:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Products not found: {missing}")
    short = [
        {"product_id": pid, "sku": products[pid].sku, "requested": qty, "available": products[pid].stock_on_hand}
        for pid, qty in quantities.items()
        if products[pid].stock_on_hand < qty
    ]
    if short:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": "Not enough stock", "items": short})

    order = Order(shop_id=shop.id, channel=body.channel, idempotency_key=idempotency_key)
    db.add(order)
    db.flush()
    for pid, qty in quantities.items():
        product = products[pid]
        product.stock_on_hand -= qty
        order.items.append(
            OrderItem(product_id=pid, quantity=qty, unit_price=product.sale_price, unit_cost=product.cost_price)
        )
        db.add(StockMovement(product_id=pid, change=-qty, reason=MovementReason.sale, order_id=order.id))
    try:
        db.commit()
    except IntegrityError:
        # Two requests with the same key raced; the other one won.
        db.rollback()
        if idempotency_key and (existing := _by_key(db, shop, idempotency_key)):
            response.status_code = status.HTTP_200_OK
            return existing
        raise
    return order


@router.get("", response_model=list[OrderOut])
def list_orders(
    channel: Channel | None = None,
    order_status: OrderStatus | None = None,
    since: datetime | None = None,
    limit: int = 50,
    shop: Shop = Depends(current_shop),
    db: Session = Depends(get_db),
) -> list[Order]:
    query = (
        select(Order)
        .where(Order.shop_id == shop.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(min(limit, 200))
    )
    if channel:
        query = query.where(Order.channel == channel)
    if order_status:
        query = query.where(Order.status == order_status)
    if since:
        query = query.where(Order.created_at >= since)
    return list(db.scalars(query))


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, shop: Shop = Depends(current_shop), db: Session = Depends(get_db)) -> Order:
    return _find_order(db, shop, order_id)


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_status(
    order_id: int, body: StatusUpdate, shop: Shop = Depends(current_shop), db: Session = Depends(get_db)
) -> Order:
    order = db.scalar(
        select(Order).where(Order.id == order_id, Order.shop_id == shop.id).with_for_update()
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Order {order_id} not found")
    if body.status not in ALLOWED[order.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Cannot move an order from {order.status.value} to {body.status.value}"
        )
    if body.status is OrderStatus.cancelled:
        items = sorted(order.items, key=lambda i: i.product_id)
        products = {
            p.id: p
            for p in db.scalars(
                select(Product).where(Product.id.in_([i.product_id for i in items])).order_by(Product.id).with_for_update()
            )
        }
        for item in items:
            products[item.product_id].stock_on_hand += item.quantity
            db.add(
                StockMovement(
                    product_id=item.product_id, change=item.quantity, reason=MovementReason.cancellation, order_id=order.id
                )
            )
    order.status = body.status
    db.commit()
    return order
