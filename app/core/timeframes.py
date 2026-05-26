"""Bybit kline interval codes and human-readable labels."""

# Supported in MVP multi-timeframe strategy
BYBIT_TIMEFRAME_LABELS: dict[str, str] = {
    "1": "1m",
    "3": "3m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "120": "2h",
    "240": "4h",
    "360": "6h",
    "720": "12h",
    "D": "1D",
    "W": "1W",
    "M": "1MN",
}


def label_for_timeframe(code: str) -> str:
    return BYBIT_TIMEFRAME_LABELS.get(code, f"{code}")
