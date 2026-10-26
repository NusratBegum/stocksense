from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, Shop
from app.schemas import ProductIn, ProductOut, ProductUpdate
from app.security import current_shop

router = APIRouter(prefix="/products", tags=["products"])


def get_product(db: Session, shop: Shop, product_id: int, *, lock: bool = False) -> Product:
    query = select(Product).where(Product.id == product_id, Product.shop_id == shop.id)
    if lock:
        query = query.with_for_update()
    product = db.scalar(query)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Product {product_id} not found")
    return product


@router.get("", response_model=list[ProductOut])
def list_products(
    low_stock: bool = False, shop: Shop = Depends(current_shop), db: Session = Depends(get_db)
) -> list[Product]:
    query = select(Product).where(Product.shop_id == shop.id).order_by(Product.sku)
    if low_stock:
        query = query.where(Product.stock_on_hand <= Product.low_stock_threshold)
    return list(db.scalars(query))


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(body: ProductIn, shop: Shop = Depends(current_shop), db: Session = Depends(get_db)) -> Product:
    product = Product(shop_id=shop.id, stock_on_hand=0, **body.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"SKU {body.sku} already exists")
    return product


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int, body: ProductUpdate, shop: Shop = Depends(current_shop), db: Session = Depends(get_db)
) -> Product:
    product = get_product(db, shop, product_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    return product
