"""Decision pipeline worker."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.bot_orchestrator import BotOrchestrator


class DecisionWorker:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._orchestrator = BotOrchestrator(session, settings)

    async def run_once(self) -> dict:
        return await self._orchestrator.run_once()
