"""Settings parsing from .env-style values."""

from app.core.config import Settings


def test_comma_separated_symbol_whitelist() -> None:
    s = Settings(symbol_whitelist="btcusdt, ethusdt , solusdt")
    assert s.symbol_whitelist == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def test_comma_separated_timeframes() -> None:
    s = Settings(timeframes="1,5,60")
    assert s.timeframes == ["1", "5", "60"]
