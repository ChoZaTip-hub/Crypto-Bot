"""ATR% helper tests."""

from app.risk.atr import atr_pct_from_timeframes


def test_atr_pct_from_timeframes() -> None:
    tfs = {
        "5": {"close": 100_000.0, "atr": 1200.0},
        "60": {"close": 99_000.0, "atr": 800.0},
    }
    assert atr_pct_from_timeframes(tfs) == 0.012


def test_atr_pct_empty() -> None:
    assert atr_pct_from_timeframes({}) == 0.0
