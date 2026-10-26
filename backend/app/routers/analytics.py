from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Order, OrderItem, OrderStatus, Product, Shop
from app.schemas import ChannelSales, DailySales, Summary
from app.security import current_shop

router = APIRouter(prefix="/analytics", tags=["analytics"])

BANGKOK = timezone(timedelta(hours=7))


@router.get("/summary", response_model=Summary)
def summary(
    days: int = Query(default=30, ge=1, le=365), shop: Shop = Depends(current_shop), db: Session = Depends(get_db)
) -> Summary:
    """Sales for the last `days` days in Bangkok time. Cancelled orders don't count."""
    start_day = datetime.now(BANGKOK).date() - timedelta(days=days - 1)
    start = datetime.combine(start_day, time.min, tzinfo=BANGKOK)
    revenue = func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0)
    cost = func.coalesce(func.sum(OrderItem.unit_cost * OrderItem.quantity), 0)
    counted = (Order.shop_id == shop.id, Order.status != OrderStatus.cancelled, Order.created_at >= start)

    by_channel = db.execute(
        select(Order.channel, func.count(func.distinct(Order.id)), revenue, cost)
        .join(OrderItem)
        .where(*counted)
        .group_by(Order.channel)
        .order_by(revenue.desc())
    ).all()

    local_day = cast(func.timezone("Asia/Bangkok", Order.created_at), Date)
    per_day = dict(
        db.execute(select(local_day, revenue).join(OrderItem).where(*counted).group_by(local_day)).all()
    )
    daily = [
        DailySales(day=(d := start_day + timedelta(days=i)).isoformat(), revenue=Decimal(per_day.get(d, 0)))
        for i in range(days)
    ]

    low_stock = db.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.shop_id == shop.id, Product.stock_on_hand <= Product.low_stock_threshold)
    )
    channels = [
        ChannelSales(channel=c, orders=n, revenue=Decimal(r), gross_profit=Decimal(r) - Decimal(k))
        for c, n, r, k in by_channel
    ]
    return Summary(
        revenue=sum((c.revenue for c in channels), Decimal("0")),
        gross_profit=sum((c.gross_profit for c in channels), Decimal("0")),
        orders=sum(c.orders for c in channels),
        low_stock=low_stock or 0,
        by_channel=channels,
        daily=daily,
    )
