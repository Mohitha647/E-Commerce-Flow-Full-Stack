from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db import get_session
from app.models import CartItem, Product, User
from app.schemas import CartItemAdd, CartItemOut, CartOut

router = APIRouter(prefix="/cart", tags=["cart"])


async def _build_cart_out(session: AsyncSession, user_id: str) -> CartOut:
    rows = (
        (
            await session.execute(
                select(CartItem, Product).join(Product, Product.id == CartItem.product_id).where(CartItem.user_id == user_id)
            )
        )
        .all()
    )
    items = [
        CartItemOut(
            product_id=p.id, product_name=p.name, unit_price=p.price,
            quantity=ci.quantity, line_total=round(p.price * ci.quantity, 2),
        )
        for ci, p in rows
    ]
    subtotal = round(sum(i.line_total for i in items), 2)
    return CartOut(items=items, subtotal=subtotal)


@router.get("", response_model=CartOut)
async def get_cart(session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> CartOut:
    return await _build_cart_out(session, user.id)


@router.post("/items", response_model=CartOut)
async def add_to_cart(
    payload: CartItemAdd,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> CartOut:
    product = await session.get(Product, payload.product_id)
    if product is None or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (
        await session.execute(
            select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == payload.product_id)
        )
    ).scalar_one_or_none()

    if existing:
        existing.quantity += payload.quantity
    else:
        session.add(CartItem(user_id=user.id, product_id=payload.product_id, quantity=payload.quantity))

    await session.commit()
    return await _build_cart_out(session, user.id)


@router.delete("/items/{product_id}", response_model=CartOut)
async def remove_from_cart(
    product_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> CartOut:
    existing = (
        await session.execute(
            select(CartItem).where(CartItem.user_id == user.id, CartItem.product_id == product_id)
        )
    ).scalar_one_or_none()
    if existing:
        await session.delete(existing)
        await session.commit()
    return await _build_cart_out(session, user.id)


@router.delete("", response_model=CartOut)
async def clear_cart(session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> CartOut:
    rows = (await session.execute(select(CartItem).where(CartItem.user_id == user.id))).scalars().all()
    for row in rows:
        await session.delete(row)
    await session.commit()
    return await _build_cart_out(session, user.id)
