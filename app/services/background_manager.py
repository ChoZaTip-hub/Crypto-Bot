"""24/7 background tasks: position monitor (SL/TP), independent of bot loop."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.session import DatabaseSessionManager
from app.services.audit_service import AuditService
from app.services.position_monitor_service import PositionMonitorService
from app.services.ratio_swap_service import RatioSwapService

logger = get_logger(__name__)


class BackgroundManager:
    """Runs position monitoring even when the trading bot is stopped."""

    def __init__(self, db_manager: DatabaseSessionManager, settings: Settings) -> None:
        self._db_manager = db_manager
        self._settings = settings
        self._running = False
        self._position_task: asyncio.Task | None = None
        self._ratio_task: asyncio.Task | None = None
        self._last_position_at: str | None = None
        self._last_position_closed: list | None = None
        self._last_ratio_at: str | None = None
        self._last_ratio_proposals: list | None = None
        self._last_error: str | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "last_position_at": self._last_position_at,
            "last_position_closed": self._last_position_closed,
            "last_error": self._last_error,
            "position_interval_seconds": self._settings.position_monitor_interval_seconds,
            "last_ratio_at": self._last_ratio_at,
            "last_ratio_proposals": self._last_ratio_proposals,
            "ratio_interval_seconds": self._settings.ratio_monitor_interval_seconds,
            "ratio_swap_enabled": self._settings.ratio_swap_enabled,
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._position_task = asyncio.create_task(self._position_loop())
        if self._settings.ratio_swap_enabled:
            self._ratio_task = asyncio.create_task(self._ratio_loop())
        logger.info("background_manager_started")

    async def stop(self) -> None:
        self._running = False
        for task in (self._position_task, self._ratio_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._position_task = None
        self._ratio_task = None
        logger.info("background_manager_stopped")

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
            except OperationalError as exc:
                self._last_error = str(exc)
                logger.warning("background_position_db_locked", error=str(exc))
            except Exception as exc:
                self._last_error = str(exc)
                logger.error("background_position_error", error=str(exc))
            await asyncio.sleep(self._settings.position_monitor_interval_seconds)

    async def _ratio_loop(self) -> None:
        while self._running:
            try:
                factory = self._db_manager.session_factory()
                async with factory() as session:
                    svc = RatioSwapService(session, self._settings, AuditService(session))
                    proposals = await svc.scan_and_propose()
                    await session.commit()
                self._last_ratio_at = datetime.now(timezone.utc).isoformat()
                self._last_ratio_proposals = proposals
                self._last_error = None
            except asyncio.CancelledError:
                break
            except OperationalError as exc:
                self._last_error = str(exc)
                logger.warning("background_ratio_db_locked", error=str(exc))
            except Exception as exc:
                self._last_error = str(exc)
                logger.error("background_ratio_error", error=str(exc))
            await asyncio.sleep(self._settings.ratio_monitor_interval_seconds)
