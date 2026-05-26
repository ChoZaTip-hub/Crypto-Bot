"""Setup scanner tests."""

from app.services.setup_scanner import _coerce_live_entry, scan_timeframe_setups


def test_coerce_live_entry_fixes_stale() -> None:
    assert _coerce_live_entry(150.0, 80.0) == 80.0
    assert _coerce_live_entry(79.5, 80.0) == 79.5


def test_scan_timeframe_setups() -> None:
    tfs = {
        "5": {"close": 100, "ema": 99, "rsi": 55, "adx": 28, "atr": 2},
        "60": {"close": 101, "ema": 98, "rsi": 40, "adx": 26, "atr": 5},
    }
    setups = scan_timeframe_setups("BNBUSDT", tfs, 80.0)
    assert setups
    assert all(s["entry"] == 80.0 for s in setups)
    assert all(s["symbol"] == "BNBUSDT" for s in setups)
