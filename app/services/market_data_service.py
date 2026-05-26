"""Market data ingestion service."""

from app.core.config import Settings
from app.core.constants import AuditEventType
from app.core.logging import get_logger
from app.db.repositories.candle_repo import CandleRepository
from app.exchanges.base import ExchangeBase
from app.exchanges.exchange_types import CandleData
from app.services.audit_service import AuditService
from app.utils.time import utc_now_ts

logger = get_logger(__name__)


class MarketDataService:
    def __init__(
        self,
        exchange: ExchangeBase,
        candle_repo: CandleRepository,
        audit: AuditService,
        settings: Settings,
    ) -> None:
        self._exchange = exchange
        self._candle_repo = candle_repo
        self._audit = audit
        self._settings = settings
        self._last_ts: dict[str, int] = {}

    async def ingest_symbol_timeframe(self, symbol: str, timeframe: str) -> int:
        candles = await self._exchange.fetch_klines(symbol, timeframe, limit=200)
        if not candles:
            return 0
        await self._candle_repo.bulk_upsert([c.to_dict() for c in candles])
        latest = candles[-1]
        self._last_ts[f"{symbol}:{timeframe}"] = latest.open_time
        await self._audit.log(
            AuditEventType.MARKET_DATA_RECEIVED,
            correlation_id=f"{symbol}:{timeframe}",
            payload={"count": len(candles), "latest_ts": latest.open_time},
        )
        return len(candles)

    async def ingest_all(self) -> dict[str, int]:
        results: dict[str, int] = {}
        for symbol in self._settings.symbol_whitelist:
            for tf in self._settings.timeframes:
                key = f"{symbol}:{tf}"
                results[key] = await self.ingest_symbol_timeframe(symbol, tf)
        return results

    async def on_candle(self, candle: CandleData) -> None:
        await self._candle_repo.bulk_upsert([candle.to_dict()])
        self._last_ts[f"{candle.symbol}:{candle.timeframe}"] = candle.open_time

    def is_data_stale(self, symbol: str, timeframe: str) -> bool:
        key = f"{symbol}:{timeframe}"
        last = self._last_ts.get(key)
        if last is None:
            return True
        return (utc_now_ts() - last) > self._settings.data_stale_seconds

    def get_last_ts(self, symbol: str, timeframe: str) -> int:
        return self._last_ts.get(f"{symbol}:{timeframe}", 0)
