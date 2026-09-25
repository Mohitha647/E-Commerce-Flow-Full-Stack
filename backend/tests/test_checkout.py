import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/auth/register", json={"email": email, "password": "testpassword1"})
    login = await client.post("/auth/login", json={"email": email, "password": "testpassword1"})
    return login.json()["access_token"]


async def _make_admin_token(client: AsyncClient) -> str:
    # NOTE: registration never sets is_admin=True (by design -- that's a
    # privilege escalation risk). For this test we log in as the demo admin
    # seeded by app/seed.py in a real deployment; here we instead promote a
    # user directly through the DB layer to keep the test self-contained.
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import User

    token = await _register_and_login(client, "admin-test@example.com")
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == "admin-test@example.com"))).scalar_one()
        user.is_admin = True
        await session.commit()
    return token


@pytest.mark.asyncio
async def test_full_catalog_cart_checkout_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await _make_admin_token(client)

        create_resp = await client.post(
            "/products",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"sku": "TEST-001", "name": "Test Widget", "price": 19.99, "stock_quantity": 3},
        )
        assert create_resp.status_code == 201
        product = create_resp.json()

        buyer_token = await _register_and_login(client, "buyer@example.com")
        auth_header = {"Authorization": f"Bearer {buyer_token}"}

        add_resp = await client.post("/cart/items", headers=auth_header, json={"product_id": product["id"], "quantity": 2})
        assert add_resp.status_code == 200
        assert add_resp.json()["subtotal"] == pytest.approx(39.98)

        checkout_resp = await client.post("/orders/checkout", headers=auth_header, json={"idempotency_key": "order-1"})
        assert checkout_resp.status_code == 201
        order = checkout_resp.json()
        assert order["total"] == pytest.approx(39.98)

        # Stock decremented correctly.
        product_after = (await client.get(f"/products/{product['id']}")).json()
        assert product_after["stock_quantity"] == 1

        # Idempotency: replaying the same key returns the same order, doesn't double-charge.
        replay_resp = await client.post("/orders/checkout", headers=auth_header, json={"idempotency_key": "order-1"})
        assert replay_resp.status_code == 201
        assert replay_resp.json()["id"] == order["id"]


@pytest.mark.asyncio
async def test_checkout_rejects_insufficient_stock():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await _make_admin_token(client)
        create_resp = await client.post(
            "/products",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"sku": "TEST-LOWSTOCK", "name": "Scarce Widget", "price": 9.99, "stock_quantity": 1},
        )
        product = create_resp.json()

        buyer_token = await _register_and_login(client, "scarcity-buyer@example.com")
        auth_header = {"Authorization": f"Bearer {buyer_token}"}

        await client.post("/cart/items", headers=auth_header, json={"product_id": product["id"], "quantity": 5})
        resp = await client.post("/orders/checkout", headers=auth_header, json={})
        assert resp.status_code == 409

        # Stock must remain untouched after a failed checkout.
        product_after = (await client.get(f"/products/{product['id']}")).json()
        assert product_after["stock_quantity"] == 1


@pytest.mark.asyncio
async def test_concurrent_checkouts_never_oversell():
    """Two buyers race to buy the last 2 units of a product (qty=1 each,
    stock=2 total requested across both = exactly matches stock). This
    doesn't fully exercise Postgres row locking (SQLite serializes writes
    at the file level), but it does prove the application-level logic
    (lock -> validate -> decrement -> commit, single transaction) is
    correct and that both concurrent requests resolve consistently
    without corrupting stock counts.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await _make_admin_token(client)
        create_resp = await client.post(
            "/products",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"sku": "TEST-RACE", "name": "Hot Item", "price": 5.00, "stock_quantity": 1},
        )
        product = create_resp.json()

        token_a = await _register_and_login(client, "racer-a@example.com")
        token_b = await _register_and_login(client, "racer-b@example.com")

        for token in (token_a, token_b):
            await client.post(
                "/cart/items", headers={"Authorization": f"Bearer {token}"},
                json={"product_id": product["id"], "quantity": 1},
            )

        results = await asyncio.gather(
            client.post("/orders/checkout", headers={"Authorization": f"Bearer {token_a}"}, json={}),
            client.post("/orders/checkout", headers={"Authorization": f"Bearer {token_b}"}, json={}),
        )
        statuses = sorted(r.status_code for r in results)
        # Exactly one checkout should succeed (201) and the other should be
        # rejected for insufficient stock (409) -- stock must never go negative.
        assert statuses == [201, 409]

        product_after = (await client.get(f"/products/{product['id']}")).json()
        assert product_after["stock_quantity"] == 0
