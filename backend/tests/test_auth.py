import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_register_login_me():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg = await client.post(
            "/auth/register", json={"email": "alice@example.com", "password": "supersecret1", "full_name": "Alice"}
        )
        assert reg.status_code == 201
        assert reg.json()["email"] == "alice@example.com"

        # duplicate registration rejected
        dup = await client.post(
            "/auth/register", json={"email": "alice@example.com", "password": "supersecret1"}
        )
        assert dup.status_code == 409

        login = await client.post("/auth/login", json={"email": "alice@example.com", "password": "supersecret1"})
        assert login.status_code == 200
        token = login.json()["access_token"]

        me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/auth/register", json={"email": "bob@example.com", "password": "correctpass1"})
        resp = await client.post("/auth/login", json={"email": "bob@example.com", "password": "wrongpass"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/cart")
        assert resp.status_code == 401
