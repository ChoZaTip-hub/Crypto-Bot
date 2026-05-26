"""Risk event repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.risk_event import RiskEvent


class RiskRepository(BaseRepository[RiskEvent]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RiskEvent)

    async def save_event(self, event: dict) -> RiskEvent:
        obj = RiskEvent(**event)
        return await self.create(obj)

    async def get_recent_events(self, limit: int = 100) -> list[RiskEvent]:
        stmt = select(RiskEvent).order_by(RiskEvent.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_level(self, level: str, limit: int = 100) -> list[RiskEvent]:
        stmt = (
            select(RiskEvent)
            .where(RiskEvent.level == level)
            .order_by(RiskEvent.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
