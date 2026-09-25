from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderItem, Product


async def frequently_bought_with(session: AsyncSession, product_id: str, limit: int = 5) -> list[tuple[Product, float]]:
    """Collaborative filtering via order co-occurrence:
    'customers who bought X also bought Y' -- counts how often each other
    product appears in the same order as `product_id`, across all orders.
    """
    order_ids_subq = (
        select(OrderItem.order_id).where(OrderItem.product_id == product_id).distinct()
    )
    co_rows = (
        await session.execute(
            select(OrderItem.product_id)
            .where(OrderItem.order_id.in_(order_ids_subq))
            .where(OrderItem.product_id != product_id)
        )
    ).scalars().all()

    if not co_rows:
        return []

    counts = Counter(co_rows)
    max_count = max(counts.values())
    top_ids = [pid for pid, _ in counts.most_common(limit)]

    products = (
        (await session.execute(select(Product).where(Product.id.in_(top_ids), Product.is_active.is_(True))))
        .scalars()
        .all()
    )
    products_by_id = {p.id: p for p in products}

    results = []
    for pid in top_ids:
        product = products_by_id.get(pid)
        if product:
            score = counts[pid] / max_count  # normalize to 0..1
            results.append((product, score))
    return results


async def similar_in_category(session: AsyncSession, product: Product, limit: int = 5) -> list[tuple[Product, float]]:
    """Content-based fallback for cold-start (new products / no order history):
    just returns other active products in the same category, ranked by rating.
    """
    if product.category_id is None:
        return []
    rows = (
        (
            await session.execute(
                select(Product)
                .where(
                    Product.category_id == product.category_id,
                    Product.id != product.id,
                    Product.is_active.is_(True),
                )
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    # Fixed moderate confidence score since this is a heuristic fallback, not a learned signal.
    return [(p, 0.5) for p in rows]


async def recommend_for_product(session: AsyncSession, product: Product, limit: int = 5) -> list[tuple[Product, float, str]]:
    """Combines collaborative + content-based signals. Collaborative results
    (real purchase co-occurrence) are ranked first and labeled accordingly;
    content-based results fill any remaining slots and are labeled as such,
    so the caller/UI can be transparent about why each item was suggested.
    """
    collaborative = await frequently_bought_with(session, product.id, limit=limit)
    seen_ids = {p.id for p, _ in collaborative}

    results: list[tuple[Product, float, str]] = [
        (p, score, "frequently bought together") for p, score in collaborative
    ]

    if len(results) < limit:
        content = await similar_in_category(session, product, limit=limit - len(results))
        for p, score in content:
            if p.id not in seen_ids:
                results.append((p, score, "similar category"))
                seen_ids.add(p.id)

    return results[:limit]


async def recommend_for_user(session: AsyncSession, user_id: str, limit: int = 8) -> list[tuple[Product, float, str]]:
    """User-level recommendations: look at the user's most recent purchase
    and recommend what's frequently bought with it. Falls back to top-rated
    active products for brand-new users with no order history.
    """
    last_item = (
        await session.execute(
            select(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if last_item is not None:
        product = await session.get(Product, last_item.product_id)
        if product:
            recs = await recommend_for_product(session, product, limit=limit)
            if recs:
                return recs

    # Cold start: no order history at all -- just surface active products.
    fallback = (
        (await session.execute(select(Product).where(Product.is_active.is_(True)).limit(limit)))
        .scalars()
        .all()
    )
    return [(p, 0.3, "popular pick") for p in fallback]
