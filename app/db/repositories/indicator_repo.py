"""Indicator repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.indicator import IndicatorValue


class IndicatorRepository(BaseRepository[IndicatorValue]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, IndicatorValue)

    async def save_values(self, values: list[dict]) -> None:
        for v in values:
            obj = IndicatorValue(**v)
            self._session.add(obj)
        await self._session.flush()

    async def get_latest(self, symbol: str, timeframe: str, name: str) -> IndicatorValue | None:
        stmt = (
            select(IndicatorValue)
            .where(
                IndicatorValue.symbol == symbol,
                IndicatorValue.timeframe == timeframe,
                IndicatorValue.name == name,
            )
            .order_by(IndicatorValue.open_time.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_symbol(
        self, symbol: str, timeframe: str, name: str, limit: int = 100
    ) -> list[IndicatorValue]:
        stmt = (
            select(IndicatorValue)
            .where(
                IndicatorValue.symbol == symbol,
                IndicatorValue.timeframe == timeframe,
                IndicatorValue.name == name,
            )
            .order_by(IndicatorValue.open_time.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
