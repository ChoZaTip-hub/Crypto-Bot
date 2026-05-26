"""ATR% helpers for volatility gates."""


def atr_pct_from_timeframes(timeframes: dict[str, dict]) -> float:
    """ATR / close on primary intraday TF (fraction, e.g. 0.012 = 1.2%)."""
    for tf in ("5", "15", "60", "240"):
        ind = timeframes.get(tf) or {}
        close = float(ind.get("close") or 0)
        atr = float(ind.get("atr") or 0)
        if close > 0 and atr > 0:
            return atr / close
    return 0.0
