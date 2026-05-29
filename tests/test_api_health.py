"""API smoke tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert "status" in r.json()


@pytest.mark.asyncio
async def test_bot_status(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/bot/status")
    assert r.status_code == 200
    body = r.json()
    assert "running" in body
    assert "auth_required" in body
