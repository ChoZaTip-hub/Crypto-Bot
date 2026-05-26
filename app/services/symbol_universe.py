"""Bybit spot symbol list for the dashboard."""

from __future__ import annotations

import time

from app.core.config import Settings
from app.core.exceptions import ExchangeError
from app.core.logging import get_logger
from app.exchanges.bybit_rest import BybitRestClient

logger = get_logger(__name__)

_cache: dict[str, tuple[float, list[str]]] = {}
_CACHE_TTL = 3600.0

# Always available offline fallback
_DEFAULT_USDT = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "DOTUSDT",
    "MATICUSDT",
    "LTCUSDT",
    "UNIUSDT",
    "ATOMUSDT",
    "NEARUSDT",
    "APTUSDT",
    "ARBUSDT",
    "OPUSDT",
    "SUIUSDT",
    "TONUSDT",
]


async def fetch_bybit_spot_usdt_symbols(
    settings: Settings,
    *,
    limit: int = 120,
) -> list[str]:
    """USDT spot pairs from Bybit (cached 1h)."""
    key = f"{settings.bybit_category}:{limit}"
    now = time.time()
    if key in _cache and now - _cache[key][0] < _CACHE_TTL:
        return _cache[key][1]

    try:
        client = BybitRestClient(settings)
        symbols = await client.list_spot_usdt_symbols(limit=limit)
        if symbols:
            _cache[key] = (now, symbols)
            return symbols
    except Exception as exc:
        logger.warning("bybit_symbols_failed", error=str(exc))

    merged = list(dict.fromkeys([*settings.symbol_whitelist, *_DEFAULT_USDT]))
    _cache[key] = (now, merged)
    return merged


async def resolve_dashboard_symbols(settings: Settings) -> list[str]:
    if settings.symbol_list_source == "whitelist":
        return list(settings.symbol_whitelist)
    top = await fetch_bybit_spot_usdt_symbols(settings, limit=settings.symbol_top_limit)
    extra = [s for s in settings.symbol_whitelist if s not in top]
    return list(dict.fromkeys([*extra, *top]))
