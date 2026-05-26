"""Mock exchange tests."""

import pytest

from app.exchanges.exchange_types import TradeOrderRequest
from app.exchanges.mock_exchange import MockExchange


@pytest.mark.asyncio
async def test_mock_fetch_klines() -> None:
    ex = MockExchange()
    await ex.connect()
    candles = await ex.fetch_klines("BTCUSDT", "5", 50)
    assert len(candles) == 50
    assert candles[0].symbol == "BTCUSDT"
    await ex.close()


@pytest.mark.asyncio
async def test_mock_place_order() -> None:
    ex = MockExchange()
    await ex.connect()
    result = await ex.place_order(
        TradeOrderRequest(symbol="BTCUSDT", side="Buy", qty=0.01)
    )
    assert result.status == "filled"
    assert result.filled_qty > 0
    await ex.close()
