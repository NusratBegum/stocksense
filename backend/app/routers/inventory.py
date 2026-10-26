from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MovementReason, Product, Shop, StockMovement
from app.routers.products import get_product
from app.schemas import MovementIn, MovementOut
from app.security import current_shop

router = APIRouter(prefix="/inventory", tags=["inventory"])

# Sales and cancellations are written by the orders router, never by hand.
MANUAL_REASONS = {MovementReason.purchase, MovementReason.adjustment, MovementReason.customer_return}


@router.post("/movements", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
def record_movement(body: MovementIn, shop: Shop = Depends(current_shop), db: Session = Depends(get_db)) -> StockMovement:
    if body.reason not in MANUAL_REASONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Sales and cancellations come from orders")
    if body.change == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Change must not be zero")
    product = get_product(db, shop, body.product_id, lock=True)
    if product.stock_on_hand + body.change < 0:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only {product.stock_on_hand} in stock")
    product.stock_on_hand += body.change
    movement = StockMovement(product_id=product.id, change=body.change, reason=body.reason, note=body.note)
    db.add(movement)
    db.commit()
    return movement


@router.get("/movements", response_model=list[MovementOut])
def list_movements(
    product_id: int | None = None, limit: int = 100, shop: Shop = Depends(current_shop), db: Session = Depends(get_db)
) -> list[StockMovement]:
    query = (
        select(StockMovement)
        .join(Product)
        .where(Product.shop_id == shop.id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(min(limit, 500))
    )
    if product_id is not None:
        query = query.where(StockMovement.product_id == product_id)
    return list(db.scalars(query))
