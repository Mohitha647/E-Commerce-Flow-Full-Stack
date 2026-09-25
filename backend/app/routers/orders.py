from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache
from app.core.deps import get_current_user
from app.db import get_session
from app.models import CartItem, InventoryLog, Order, OrderItem, OrderStatus, Product, User
from app.schemas import CheckoutRequest, OrderItemOut, OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])


def _order_to_out(order: Order, items: list[OrderItem], products_by_id: dict[str, Product]) -> OrderOut:
    item_outs = [
        OrderItemOut(
            product_id=oi.product_id,
            product_name=products_by_id[oi.product_id].name if oi.product_id in products_by_id else "(removed)",
            quantity=oi.quantity,
            unit_price=oi.unit_price_cents / 100,
            line_total=round(oi.quantity * oi.unit_price_cents / 100, 2),
        )
        for oi in items
    ]
    return OrderOut(id=order.id, status=order.status, total=order.total, created_at=order.created_at, items=item_outs)


@router.post("/checkout", response_model=OrderOut, status_code=201)
async def checkout(
    payload: CheckoutRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> OrderOut:
    """
    Places an order from the user's current cart.

    Concurrency safety: every product row touched is locked with
    `SELECT ... FOR UPDATE` (a real row-level lock on Postgres; SQLite
    serializes writes at the database-file level so it is effectively
    equivalent there) *before* stock is checked and decremented, all
    inside one transaction. This prevents the classic race condition
    where two simultaneous checkouts both read "stock = 1" and both
    successfully decrement it to -1. Products are locked in a stable
    order (sorted by id) to avoid deadlocks between concurrent checkouts
    that share overlapping products.
    """
    # Idempotency: replaying the same request (e.g. a client retry after a
    # timeout) returns the original order instead of double-charging.
    if payload.idempotency_key:
        existing = (
            await session.execute(
                select(Order).where(Order.user_id == user.id, Order.idempotency_key == payload.idempotency_key)
            )
        ).scalar_one_or_none()
        if existing:
            items = (await session.execute(select(OrderItem).where(OrderItem.order_id == existing.id))).scalars().all()
            products = (await session.execute(select(Product).where(Product.id.in_([i.product_id for i in items])))).scalars().all()
            return _order_to_out(existing, items, {p.id: p for p in products})

    cart_rows = (await session.execute(select(CartItem).where(CartItem.user_id == user.id))).scalars().all()
    if not cart_rows:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Lock every product row involved, in a deterministic order (by id) to
    # prevent deadlocks if two checkouts share products but request them
    # via different cart orderings.
    product_ids = sorted({c.product_id for c in cart_rows})
    locked_products = (
        (
            await session.execute(
                select(Product).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update()
            )
        )
        .scalars()
        .all()
    )
    products_by_id = {p.id: p for p in locked_products}

    # Validate availability for the whole cart BEFORE mutating anything,
    # so a failure leaves stock untouched and we can report all problems at once.
    problems = []
    for cart_item in cart_rows:
        product = products_by_id.get(cart_item.product_id)
        if product is None or not product.is_active:
            problems.append(f"Product {cart_item.product_id} is no longer available")
        elif product.stock_quantity < cart_item.quantity:
            problems.append(
                f"Insufficient stock for '{product.name}': requested {cart_item.quantity}, have {product.stock_quantity}"
            )
    if problems:
        raise HTTPException(status_code=409, detail={"message": "Checkout failed", "problems": problems})

    order = Order(user_id=user.id, status=OrderStatus.paid.value, idempotency_key=payload.idempotency_key)
    session.add(order)
    await session.flush()  # assign order.id

    total_cents = 0
    order_items: list[OrderItem] = []
    for cart_item in cart_rows:
        product = products_by_id[cart_item.product_id]
        product.stock_quantity -= cart_item.quantity
        session.add(
            InventoryLog(
                product_id=product.id, delta=-cart_item.quantity, reason=f"order:{order.id}",
                resulting_quantity=product.stock_quantity,
            )
        )
        order_item = OrderItem(
            order_id=order.id, product_id=product.id, quantity=cart_item.quantity,
            unit_price_cents=product.price_cents,
        )
        session.add(order_item)
        order_items.append(order_item)
        total_cents += cart_item.quantity * product.price_cents

    order.total_cents = total_cents

    for cart_item in cart_rows:
        await session.delete(cart_item)

    await session.commit()
    await session.refresh(order)

    cache = get_cache()
    await cache.invalidate_prefix("products:list")
    for pid in product_ids:
        await cache.invalidate_prefix(f"products:detail:{pid}")

    return _order_to_out(order, order_items, products_by_id)


@router.get("", response_model=list[OrderOut])
async def list_orders(session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> list[OrderOut]:
    orders = (
        (await session.execute(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())))
        .scalars()
        .all()
    )
    out = []
    for order in orders:
        items = (await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars().all()
        products = (
            (await session.execute(select(Product).where(Product.id.in_([i.product_id for i in items]))))
            .scalars()
            .all()
        )
        out.append(_order_to_out(order, items, {p.id: p for p in products}))
    return out


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> OrderOut:
    order = await session.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    items = (await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars().all()
    products = (
        (await session.execute(select(Product).where(Product.id.in_([i.product_id for i in items]))))
        .scalars()
        .all()
    )
    return _order_to_out(order, items, {p.id: p for p in products})
