"""24/7 background tasks: news + position monitor (independent of bot loop)."""

import asyncio
from datetime import datetime, timezone

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.session import DatabaseSessionManager
from app.services.audit_service import AuditService
from app.services.news_service import NewsService
from app.services.position_monitor_service import PositionMonitorService
from app.services.sentiment_service import SentimentService

logger = get_logger(__name__)


class BackgroundManager:
    """Runs news ingestion and position monitoring even when trading bot is stopped."""

    def __init__(self, db_manager: DatabaseSessionManager, settings: Settings) -> None:
        self._db_manager = db_manager
        self._settings = settings
        self._running = False
        self._news_task: asyncio.Task | None = None
        self._position_task: asyncio.Task | None = None
        self._last_news_at: str | None = None
        self._last_news_counts: dict | None = None
        self._last_position_at: str | None = None
        self._last_position_closed: list | None = None
        self._last_error: str | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "last_news_at": self._last_news_at,
            "last_news_counts": self._last_news_counts,
            "last_position_at": self._last_position_at,
            "last_position_closed": self._last_position_closed,
            "last_error": self._last_error,
            "news_interval_seconds": self._settings.news_poll_interval_seconds,
            "position_interval_seconds": self._settings.position_monitor_interval_seconds,
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._news_task = asyncio.create_task(self._news_loop())
        self._position_task = asyncio.create_task(self._position_loop())
        logger.info("background_manager_started")

    async def stop(self) -> None:
        self._running = False
        for task in (self._news_task, self._position_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._news_task = None
        self._position_task = None
        logger.info("background_manager_stopped")

    async def _news_loop(self) -> None:
        while self._running:
            try:
                factory = self._db_manager.session_factory()
                async with factory() as session:
                    audit = AuditService(session)
                    news = NewsService(session, audit, self._settings)
                    sentiment = SentimentService(session, audit)
                    counts = await news.ingest_all()
                    await sentiment.score_recent_news(self._settings.symbol_whitelist)
                    await session.commit()
                self._last_news_at = datetime.now(timezone.utc).isoformat()
                self._last_news_counts = counts
                self._last_error = None
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._last_error = str(exc)
                logger.error("background_news_error", error=str(exc))
            await asyncio.sleep(self._settings.news_poll_interval_seconds)

    async def _position_loop(self) -> None:
        while self._running:
            try:
                factory = self._db_manager.session_factory()
                async with factory() as session:
                    monitor = PositionMonitorService(session, self._settings)
                    closed = await monitor.tick()
                    await session.commit()
                self._last_position_at = datetime.now(timezone.utc).isoformat()
                self._last_position_closed = closed
                self._last_error = None
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._last_error = str(exc)
                logger.error("background_position_error", error=str(exc))
            await asyncio.sleep(self._settings.position_monitor_interval_seconds)
