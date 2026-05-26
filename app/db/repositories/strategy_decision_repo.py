"""Strategy decision repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.strategy_decision import StrategyDecision


class StrategyDecisionRepository(BaseRepository[StrategyDecision]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StrategyDecision)

    async def save_decision(self, decision: dict) -> StrategyDecision:
        obj = StrategyDecision(**decision)
        return await self.create(obj)

    async def get_by_signal_id(self, signal_id: int) -> list[StrategyDecision]:
        stmt = select(StrategyDecision).where(StrategyDecision.signal_id == signal_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(self, limit: int = 100) -> list[StrategyDecision]:
        stmt = (
            select(StrategyDecision).order_by(StrategyDecision.created_at.desc()).limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_by_symbol(self, symbol: str, limit: int = 10) -> list[StrategyDecision]:
        stmt = (
            select(StrategyDecision)
            .where(StrategyDecision.symbol == symbol)
            .order_by(StrategyDecision.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_correlation_id(self, correlation_id: str) -> list[StrategyDecision]:
        stmt = (
            select(StrategyDecision)
            .where(StrategyDecision.correlation_id == correlation_id)
            .order_by(StrategyDecision.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
