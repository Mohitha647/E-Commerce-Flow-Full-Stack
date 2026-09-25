"""
Populates the database with demo categories, products, a demo user, and a
couple of past orders (so the recommendation engine has co-occurrence data
to work with immediately).

Usage:
    python -m app.seed
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db import AsyncSessionLocal, init_db
from app.models import Category, InventoryLog, Order, OrderItem, OrderStatus, Product, User

CATEGORIES = ["Electronics", "Home & Kitchen", "Books", "Sports & Outdoors"]

PRODUCTS = [
    # (sku, name, description, price, category, stock)
    ("ELEC-001", "Wireless Noise-Cancelling Headphones", "Over-ear, 30hr battery.", 179.99, "Electronics", 40),
    ("ELEC-002", "USB-C Fast Charger 65W", "GaN charger, compact.", 29.99, "Electronics", 120),
    ("ELEC-003", "4K Webcam", "1080p60/4K30, autofocus.", 89.99, "Electronics", 25),
    ("HOME-001", "Stainless Steel French Press", "34oz, double-wall.", 34.99, "Home & Kitchen", 60),
    ("HOME-002", "Non-Stick Ceramic Pan Set (3pc)", "PFOA-free coating.", 64.99, "Home & Kitchen", 35),
    ("BOOK-001", "Deep Work", "Cal Newport, productivity.", 14.99, "Books", 100),
    ("BOOK-002", "The Pragmatic Programmer", "20th anniversary edition.", 39.99, "Books", 70),
    ("SPRT-001", "Adjustable Dumbbell Set", "5-25kg per hand.", 149.99, "Sports & Outdoors", 15),
    ("SPRT-002", "Yoga Mat Pro", "6mm, non-slip.", 24.99, "Sports & Outdoors", 90),
]


async def seed() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        existing = (await session.execute(select(User).where(User.email == "demo@commerceflow.dev"))).scalar_one_or_none()
        if existing:
            print("Seed data already present -- skipping. (Delete the DB file / volume to reseed.)")
            return

        cat_by_name: dict[str, Category] = {}
        for name in CATEGORIES:
            cat = Category(name=name, slug=name.lower().replace(" & ", "-").replace(" ", "-"))
            session.add(cat)
            cat_by_name[name] = cat
        await session.flush()

        product_by_sku: dict[str, Product] = {}
        for sku, name, desc, price, cat_name, stock in PRODUCTS:
            p = Product(
                sku=sku, name=name, description=desc, price_cents=round(price * 100),
                category_id=cat_by_name[cat_name].id, stock_quantity=stock,
            )
            session.add(p)
            product_by_sku[sku] = p
        await session.flush()

        demo_user = User(
            email="demo@commerceflow.dev",
            hashed_password=hash_password("demopassword123"),
            full_name="Demo User",
        )
        admin_user = User(
            email="admin@commerceflow.dev",
            hashed_password=hash_password("adminpassword123"),
            full_name="Admin User",
            is_admin=True,
        )
        session.add_all([demo_user, admin_user])
        await session.flush()

        # A past order so "frequently bought together" has real data:
        # headphones + charger were bought together twice.
        for _ in range(2):
            order = Order(user_id=demo_user.id, status=OrderStatus.paid.value)
            session.add(order)
            await session.flush()
            total = 0
            for sku, qty in [("ELEC-001", 1), ("ELEC-002", 1)]:
                p = product_by_sku[sku]
                session.add(OrderItem(order_id=order.id, product_id=p.id, quantity=qty, unit_price_cents=p.price_cents))
                session.add(
                    InventoryLog(
                        product_id=p.id, delta=-qty, reason=f"seed-order:{order.id}",
                        resulting_quantity=p.stock_quantity - qty,
                    )
                )
                p.stock_quantity -= qty
                total += qty * p.price_cents
            order.total_cents = total

        await session.commit()
        print("Seed complete:")
        print(f"  Demo user:  demo@commerceflow.dev  / demopassword123")
        print(f"  Admin user: admin@commerceflow.dev / adminpassword123")
        print(f"  {len(PRODUCTS)} products across {len(CATEGORIES)} categories")


if __name__ == "__main__":
    asyncio.run(seed())
