"""Integration test: Bybit announcements via pybit (optional live call)."""

import os

import pytest

from app.core.config import Settings
from app.exchanges.bybit_rest import BybitRestClient
from app.news.bybit_announcements import parse_announcement_rows


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pybit_get_announcement_live() -> None:
    """Skipped unless RUN_BYBIT_LIVE_TESTS=1 (hits Bybit public API)."""
    if os.getenv("RUN_BYBIT_LIVE_TESTS") != "1":
        pytest.skip("Set RUN_BYBIT_LIVE_TESTS=1 to run live Bybit announcement test")

    settings = Settings(bybit_testnet=True)
    client = BybitRestClient(settings)
    data = await client.get_announcement(locale="en-US", limit=1)

    assert data["retCode"] == 0
    assert data["retMsg"] == "OK"
    rows = data["result"]["list"]
    assert len(rows) >= 1
    items = parse_announcement_rows(rows)
    assert items[0].title
    assert items[0].source == "Bybit Announcements"
