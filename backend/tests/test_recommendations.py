import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _login(client, email, password="testpassword1", register=True):
    if register:
        await client.post("/auth/register", json={"email": email, "password": password})
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_frequently_bought_together_recommendation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        from sqlalchemy import select
        from app.db import AsyncSessionLocal
        from app.models import User

        admin_token = await _login(client, "rec-admin@example.com")
        async with AsyncSessionLocal() as session:
            user = (await session.execute(select(User).where(User.email == "rec-admin@example.com"))).scalar_one()
            user.is_admin = True
            await session.commit()

        headers = {"Authorization": f"Bearer {admin_token}"}
        p1 = (
            await client.post("/products", headers=headers, json={"sku": "REC-A", "name": "Product A", "price": 10, "stock_quantity": 10})
        ).json()
        p2 = (
            await client.post("/products", headers=headers, json={"sku": "REC-B", "name": "Product B", "price": 20, "stock_quantity": 10})
        ).json()

        buyer_token = await _login(client, "rec-buyer@example.com")
        buyer_headers = {"Authorization": f"Bearer {buyer_token}"}

        # Buy both products together so they become "frequently bought together".
        await client.post("/cart/items", headers=buyer_headers, json={"product_id": p1["id"], "quantity": 1})
        await client.post("/cart/items", headers=buyer_headers, json={"product_id": p2["id"], "quantity": 1})
        checkout = await client.post("/orders/checkout", headers=buyer_headers, json={})
        assert checkout.status_code == 201

        recs_resp = await client.get(f"/recommendations/products/{p1['id']}")
        assert recs_resp.status_code == 200
        recs = recs_resp.json()
        assert any(r["product"]["id"] == p2["id"] and r["reason"] == "frequently bought together" for r in recs)


@pytest.mark.asyncio
async def test_recommend_for_me_cold_start_returns_something():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client, "cold-start-user@example.com")
        resp = await client.get("/recommendations/for-me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        # Should not error even with zero order history -- falls back gracefully.
        assert isinstance(resp.json(), list)
