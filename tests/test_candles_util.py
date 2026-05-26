"""Candle filter tests."""

from app.utils.candles import filter_price_outliers, sanitize_ohlc_rows


def test_filter_price_outliers_removes_spike() -> None:
    series = [
        {"time": 1, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1},
        {"time": 2, "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1},
        {"time": 3, "open": 100, "high": 150, "low": 99, "close": 149, "volume": 1},
        {"time": 4, "open": 100, "high": 101, "low": 99, "close": 100.2, "volume": 1},
    ]
    for i in range(5, 12):
        series.append(
            {"time": i, "open": 100, "high": 101, "low": 99, "close": 100 + i * 0.01, "volume": 1}
        )
    kept, removed = filter_price_outliers(series, max_dev_pct=5.0)
    assert removed >= 1
    assert all(c["high"] < 110 for c in kept)


def test_sanitize_ohlc_rows() -> None:
    rows = [
        {"symbol": "X", "timeframe": "5", "open_time": i, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1}
        for i in range(8)
    ]
    rows.append(
        {"symbol": "X", "timeframe": "5", "open_time": 9, "open": 100, "high": 200, "low": 99, "close": 180, "volume": 1}
    )
    out = sanitize_ohlc_rows(rows, max_dev_pct=5.0)
    assert len(out) == 8
