"""Pytest fixtures."""

import pytest

from app.core.config import Settings
from app.core.constants import TradingMode


@pytest.fixture
def settings() -> Settings:
    return Settings(
        trading_mode=TradingMode.PAPER,
        live_trading_enabled=False,
        database_url="sqlite+aiosqlite:///:memory:",
        symbol_whitelist=["BTCUSDT"],
        timeframes=["5", "60"],
    )
