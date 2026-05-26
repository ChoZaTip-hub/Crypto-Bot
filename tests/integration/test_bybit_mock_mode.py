"""Bybit client integration tests (no live calls)."""

import pytest

from app.core.config import Settings
from app.core.exceptions import LiveTradingDisabledError
from app.exchanges.bybit_client import BybitClient
from app.exchanges.exchange_types import TradeOrderRequest


@pytest.mark.asyncio
async def test_live_order_blocked_by_default() -> None:
    settings = Settings(
        trading_mode="paper",
        live_trading_enabled=False,
        bybit_testnet=True,
    )
    client = BybitClient(settings)
    with pytest.raises(LiveTradingDisabledError):
        await client.place_order(
            TradeOrderRequest(symbol="BTCUSDT", side="Buy", qty=0.001)
        )


def test_bybit_client_instantiation() -> None:
    settings = Settings(bybit_testnet=True)
    client = BybitClient(settings)
    assert client is not None
