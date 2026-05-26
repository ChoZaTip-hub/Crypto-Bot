"""Singleton bot runner — survives across HTTP requests."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.session import DatabaseSessionManager
from app.services.bot_orchestrator import BotOrchestrator

logger = get_logger(__name__)


class BotManager:
    """Keeps the trading loop alive in the background with per-iteration DB sessions."""

    def __init__(self, db_manager: DatabaseSessionManager, settings: Settings) -> None:
        self._db_manager = db_manager
        self._settings = settings
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_run_at: str | None = None
        self._last_error: str | None = None
        self._last_result: dict | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_run_at(self) -> str | None:
        return self._last_run_at

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def last_result(self) -> dict | None:
        return self._last_result

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(run_immediately=True))
        logger.info("bot_manager_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("bot_manager_stopped")

    async def run_once(self) -> dict:
        result = await self._execute_cycle()
        return result

    async def _loop(self, *, run_immediately: bool = False) -> None:
        first = run_immediately
        while self._running:
            try:
                await self._execute_cycle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._last_error = str(exc)
                logger.error("bot_loop_error", error=str(exc))
            if not first:
                await asyncio.sleep(self._settings.market_poll_interval_seconds)
            first = False

    async def _execute_cycle(self) -> dict:
        last_exc: Exception | None = None
        for attempt in range(5):
            try:
                factory = self._db_manager.session_factory()
                async with factory() as session:
                    orchestrator = BotOrchestrator(session, self._settings)
                    result = await orchestrator.run_pipeline()
                    await session.commit()
                self._last_run_at = datetime.now(timezone.utc).isoformat()
                self._last_error = None
                self._last_result = result
                return result
            except OperationalError as exc:
                last_exc = exc
                if "locked" not in str(exc).lower():
                    raise
                await asyncio.sleep(0.3 * (attempt + 1))
        assert last_exc is not None
        raise last_exc
