"""Execution worker stub."""

from app.core.logging import get_logger

logger = get_logger(__name__)


class ExecutionWorker:
    """Processes pending orders — delegated to BotOrchestrator in MVP."""

    async def tick(self) -> None:
        logger.debug("execution_worker_tick")
