"""Portfolio repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.portfolio import PortfolioSnapshot


class PortfolioRepository(BaseRepository[PortfolioSnapshot]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PortfolioSnapshot)

    async def save_snapshot(self, snapshot: dict) -> PortfolioSnapshot:
        obj = PortfolioSnapshot(**snapshot)
        return await self.create(obj)

    async def get_latest(self) -> PortfolioSnapshot | None:
        stmt = select(PortfolioSnapshot).order_by(PortfolioSnapshot.created_at.desc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_history(self, limit: int = 200) -> list[PortfolioSnapshot]:
        stmt = (
            select(PortfolioSnapshot).order_by(PortfolioSnapshot.created_at.desc()).limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
