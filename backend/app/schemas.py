from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Channel, MovementReason, OrderStatus


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    shop_name: str = Field(min_length=1, max_length=100)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    cost_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    sale_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    low_stock_threshold: int = Field(default=5, ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    sale_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    low_stock_threshold: int | None = Field(default=None, ge=0)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    cost_price: Decimal
    sale_price: Decimal
    stock_on_hand: int
    low_stock_threshold: int
    is_low_stock: bool


class MovementIn(BaseModel):
    product_id: int
    change: int = Field(description="Positive to add stock, negative to remove it")
    reason: MovementReason
    note: str | None = Field(default=None, max_length=200)


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    change: int
    reason: MovementReason
    order_id: int | None
    note: str | None
    created_at: datetime


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderIn(BaseModel):
    channel: Channel
    items: list[OrderItemIn] = Field(min_length=1)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    quantity: int
    unit_price: Decimal


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: Channel
    status: OrderStatus
    created_at: datetime
    items: list[OrderItemOut]
    total: Decimal


class StatusUpdate(BaseModel):
    status: OrderStatus


class ChannelSales(BaseModel):
    channel: Channel
    orders: int
    revenue: Decimal
    gross_profit: Decimal


class DailySales(BaseModel):
    day: str
    revenue: Decimal


class Summary(BaseModel):
    revenue: Decimal
    gross_profit: Decimal
    orders: int
    low_stock: int
    by_channel: list[ChannelSales]
    daily: list[DailySales]
