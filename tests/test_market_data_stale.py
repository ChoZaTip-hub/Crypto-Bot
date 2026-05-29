"""Data freshness checks."""

from app.core.config import Settings
from app.services.market_data_service import MarketDataService


def test_data_not_stale_within_candle_window() -> None:
    from app.utils.time import utc_now_ts

    settings = Settings(data_stale_seconds=120)
    svc = MarketDataService(None, None, None, settings)  # type: ignore[arg-type]
    now = utc_now_ts()
    # Last 5m candle closed 2 minutes ago — still fresh
    svc._last_close_ts["BTCUSDT:5"] = now - 120
    assert svc.is_data_stale("BTCUSDT", "5") is False


def test_data_stale_after_missed_candle() -> None:
    from app.utils.time import utc_now_ts

    settings = Settings(data_stale_seconds=120)
    svc = MarketDataService(None, None, None, settings)  # type: ignore[arg-type]
    now = utc_now_ts()
    # Last close was 10 minutes ago on 5m TF — stale
    svc._last_close_ts["BTCUSDT:5"] = now - 600
    assert svc.is_data_stale("BTCUSDT", "5") is True
