"""Strategy engine unit tests."""

import pytest

from app.core.constants import SignalAction
from app.strategies.base import StrategyInputs
from app.strategies.multi_timeframe_strategy import MultiTimeframeStrategy


@pytest.mark.asyncio
async def test_multi_timeframe_returns_signal() -> None:
    strategy = MultiTimeframeStrategy()
    inputs = StrategyInputs(
        symbol="BTCUSDT",
        timeframes={
            "60": {
                "close": 100.0,
                "ema": 98.0,
                "adx": 30.0,
                "atr": 2.0,
                "bb_width": 0.05,
            },
            "5": {
                "close": 100.0,
                "rsi": 25.0,
                "bb_lower": 99.0,
                "bb_upper": 101.0,
                "atr": 1.0,
            },
        },
    )
    signal = await strategy.decide(inputs)
    assert signal.symbol == "BTCUSDT"
    assert signal.action in (SignalAction.BUY, SignalAction.SELL, SignalAction.HOLD)
    assert signal.correlation_id
    assert signal.reason

