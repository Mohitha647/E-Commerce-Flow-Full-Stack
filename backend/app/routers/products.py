from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache
from app.core.deps import get_current_admin, get_current_user
from app.db import get_session
from app.models import Category, InventoryLog, Product, Review, User
from app.schemas import (
    CategoryOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    RestockRequest,
    ReviewCreate,
    ReviewOut,
)

router = APIRouter(tags=["catalog"])


async def build_product_out(session: AsyncSession, product: Product) -> ProductOut:
    agg = (
        await session.execute(
            select(func.avg(Review.rating), func.count(Review.id)).where(Review.product_id == product.id)
        )
    ).one()
    avg_rating, review_count = agg
    data = ProductOut.model_validate(product).model_dump()
    data["avg_rating"] = round(avg_rating, 2) if avg_rating is not None else None
    data["review_count"] = review_count or 0
    return ProductOut(**data)


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(session: AsyncSession = Depends(get_session)) -> list[CategoryOut]:
    rows = (await session.execute(select(Category))).scalars().all()
    return [CategoryOut.model_validate(c) for c in rows]


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    category_id: Optional[str] = None,
    search: Optional[str] = Query(default=None, min_length=1),
    active_only: bool = True,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[ProductOut]:
    cache = get_cache()
    cache_key = f"products:list:{category_id}:{search}:{active_only}:{limit}:{offset}"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return [ProductOut(**row) for row in cached]

    stmt = select(Product)
    if active_only:
        stmt = stmt.where(Product.is_active.is_(True))
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))
    stmt = stmt.offset(offset).limit(limit)

    rows = (await session.execute(stmt)).scalars().all()
    results = [await build_product_out(session, p) for p in rows]

    await cache.set_json(cache_key, [r.model_dump() for r in results])
    return results


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, session: AsyncSession = Depends(get_session)) -> ProductOut:
    cache = get_cache()
    cache_key = f"products:detail:{product_id}"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return ProductOut(**cached)

    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    result = await build_product_out(session, product)
    await cache.set_json(cache_key, result.model_dump())
    return result


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_current_admin),
) -> ProductOut:
    existing = (await session.execute(select(Product).where(Product.sku == payload.sku))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="SKU already exists")

    product = Product(
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        price_cents=round(payload.price * 100),
        category_id=payload.category_id,
        stock_quantity=payload.stock_quantity,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)

    await get_cache().invalidate_prefix("products:list")
    return await build_product_out(session, product)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_current_admin),
) -> ProductOut:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = payload.model_dump(exclude_unset=True)
    if "price" in updates:
        product.price_cents = round(updates.pop("price") * 100)
    for field, value in updates.items():
        setattr(product, field, value)

    await session.commit()
    await session.refresh(product)

    cache = get_cache()
    await cache.invalidate_prefix("products:list")
    await cache.invalidate_prefix(f"products:detail:{product_id}")
    return await build_product_out(session, product)


@router.post("/products/{product_id}/restock", response_model=ProductOut)
async def restock_product(
    product_id: str,
    payload: RestockRequest,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(get_current_admin),
) -> ProductOut:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    product.stock_quantity += payload.quantity
    session.add(
        InventoryLog(
            product_id=product.id, delta=payload.quantity, reason=payload.reason,
            resulting_quantity=product.stock_quantity,
        )
    )
    await session.commit()
    await session.refresh(product)

    cache = get_cache()
    await cache.invalidate_prefix("products:list")
    await cache.invalidate_prefix(f"products:detail:{product_id}")
    return await build_product_out(session, product)


@router.post("/products/{product_id}/reviews", response_model=ReviewOut, status_code=201)
async def add_review(
    product_id: str,
    payload: ReviewCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ReviewOut:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (
        await session.execute(
            select(Review).where(Review.user_id == user.id, Review.product_id == product_id)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="You already reviewed this product")

    review = Review(user_id=user.id, product_id=product_id, rating=payload.rating, comment=payload.comment)
    session.add(review)
    await session.commit()
    await session.refresh(review)

    await get_cache().invalidate_prefix(f"products:detail:{product_id}")
    return ReviewOut.model_validate(review)


@router.get("/products/{product_id}/reviews", response_model=list[ReviewOut])
async def list_reviews(product_id: str, session: AsyncSession = Depends(get_session)) -> list[ReviewOut]:
    rows = (await session.execute(select(Review).where(Review.product_id == product_id))).scalars().all()
    return [ReviewOut.model_validate(r) for r in rows]
