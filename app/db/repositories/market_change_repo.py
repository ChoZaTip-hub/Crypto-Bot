"""Market change repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.market_change import MarketChange


class MarketChangeRepository(BaseRepository[MarketChange]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MarketChange)

    async def save_change(self, change: dict) -> MarketChange:
        return await self.create(MarketChange(**change))

    async def get_recent(
        self, symbol: str | None = None, limit: int = 50
    ) -> list[MarketChange]:
        stmt = select(MarketChange).order_by(MarketChange.created_at.desc()).limit(limit)
        if symbol:
            stmt = stmt.where(MarketChange.symbol == symbol)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
