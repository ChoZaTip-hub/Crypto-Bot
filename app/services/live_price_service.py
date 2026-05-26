"""Live mark price from Bybit mainnet (same market as TradingView BYBIT:*)."""

from app.core.config import Settings
from app.core.logging import get_logger
from app.exchanges.bybit_client import BybitClient

logger = get_logger(__name__)


async def fetch_display_price(symbol: str, settings: Settings) -> dict:
    """Real-time ticker for dashboard — always Bybit mainnet spot."""
    symbol = symbol.upper()
    out: dict = {
        "symbol": symbol,
        "price": 0.0,
        "source": "unavailable",
        "tradingview_symbol": f"BYBIT:{symbol}",
    }

    if not settings.use_bybit_market_data:
        return out

    try:
        price = await BybitClient(settings).fetch_last_price(symbol)
        if price > 0:
            out["price"] = price
            out["source"] = "bybit_live"
    except Exception as exc:
        logger.warning("live_price_failed", symbol=symbol, error=str(exc))

    return out


async def fetch_live_price(symbol: str, settings: Settings) -> tuple[float, str]:
    info = await fetch_display_price(symbol, settings)
    return float(info.get("price") or 0), str(info.get("source") or "unavailable")
