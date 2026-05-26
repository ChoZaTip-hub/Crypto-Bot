"""Market data worker."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.candle_repo import CandleRepository
from app.exchanges.mock_exchange import MockExchange
from app.services.audit_service import AuditService
from app.services.market_data_service import MarketDataService

logger = get_logger(__name__)


class MarketWorker:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        exchange = MockExchange()
        self._exchange = exchange
        self._service = MarketDataService(
            exchange,
            CandleRepository(session),
            AuditService(session),
            settings,
        )
        self._settings = settings
        self._running = False

    async def start(self) -> None:
        await self._exchange.connect()
        self._running = True
        while self._running:
            await self._service.ingest_all()
            await asyncio.sleep(self._settings.market_poll_interval_seconds)

    async def stop(self) -> None:
        self._running = False
        await self._exchange.close()
