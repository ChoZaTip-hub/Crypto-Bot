"""Market data ingestion service."""

from app.core.config import Settings
from app.core.constants import AuditEventType
from app.core.logging import get_logger
from app.db.repositories.candle_repo import CandleRepository
from app.exchanges.base import ExchangeBase
from app.exchanges.exchange_types import CandleData
from app.services.audit_service import AuditService
from app.utils.candles import sanitize_ohlc_rows
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
        self._last_close_ts: dict[str, int] = {}

    async def ingest_symbol_timeframe(self, symbol: str, timeframe: str) -> int:
        candles = await self._exchange.fetch_klines(symbol, timeframe, limit=200)
        if not candles:
            return 0
        rows = sanitize_ohlc_rows([c.to_dict() for c in candles])
        if not rows:
            return 0
        await self._candle_repo.bulk_upsert(rows)
        latest = candles[-1]
        key = f"{symbol}:{timeframe}"
        self._last_close_ts[key] = int(latest.close_time or latest.open_time)
        await self._audit.log(
            AuditEventType.MARKET_DATA_RECEIVED,
            correlation_id=f"{symbol}:{timeframe}",
            payload={"count": len(candles), "latest_close_ts": self._last_close_ts[key]},
        )
        return len(candles)

    async def ingest_all(self) -> dict[str, int]:
        return await self._ingest_pairs(
            self._settings.symbol_whitelist,
            self._settings.timeframes,
        )

    async def ingest_cycle(self, symbols: list[str] | None = None) -> dict[str, int]:
        """Light ingest for bot loop (fewer API calls)."""
        syms = symbols or self._settings.symbol_whitelist
        return await self._ingest_pairs(syms, self._settings.bot_cycle_timeframes)

    async def ingest_symbol_tf(self, symbol: str, timeframe: str) -> dict[str, int]:
        key = f"{symbol}:{timeframe}"
        count = await self.ingest_symbol_timeframe(symbol, timeframe)
        return {key: count}

    async def _ingest_pairs(self, symbols: list[str], timeframes: list[str]) -> dict[str, int]:
        """Sequential ingest; commit per symbol on SQLite to avoid long locks."""
        results: dict[str, int] = {}
        session = self._candle_repo._session
        is_sqlite = str(session.get_bind().dialect.name) == "sqlite"

        for symbol in symbols:
            for tf in timeframes:
                key = f"{symbol}:{tf}"
                try:
                    results[key] = await self.ingest_symbol_timeframe(symbol, tf)
                except Exception as exc:
                    logger.warning("ingest_failed", key=key, error=str(exc))
                    results[key] = 0
            if is_sqlite:
                try:
                    await session.commit()
                except Exception as exc:
                    logger.warning("ingest_commit_failed", symbol=symbol, error=str(exc))
                    await session.rollback()
        return results

    async def on_candle(self, candle: CandleData) -> None:
        await self._candle_repo.bulk_upsert([candle.to_dict()])
        key = f"{candle.symbol}:{candle.timeframe}"
        self._last_close_ts[key] = int(candle.close_time or candle.open_time)

    def is_data_stale(self, symbol: str, timeframe: str) -> bool:
        from app.core.timeframes import seconds_for_timeframe

        key = f"{symbol}:{timeframe}"
        last_close = self._last_close_ts.get(key)
        if last_close is None:
            return True
        interval = seconds_for_timeframe(timeframe)
        buffer = max(self._settings.data_stale_seconds, interval // 2)
        # Stale when current time is past expected next candle close + buffer
        expected_next_close = last_close + interval
        return utc_now_ts() > expected_next_close + buffer

    def get_last_ts(self, symbol: str, timeframe: str) -> int:
        return self._last_close_ts.get(f"{symbol}:{timeframe}", 0)
