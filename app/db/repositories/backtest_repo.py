"""Backtest repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.backtest import BacktestResult, BacktestTrade


class BacktestRepository(BaseRepository[BacktestResult]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, BacktestResult)

    async def save_result(self, result: dict) -> BacktestResult:
        obj = BacktestResult(**result)
        return await self.create(obj)

    async def get_by_id(self, backtest_id: int) -> BacktestResult | None:
        return await super().get_by_id(backtest_id)

    async def get_recent(self, limit: int = 20) -> list[BacktestResult]:
        stmt = select(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def save_trade_rows(self, backtest_id: int, rows: list[dict]) -> None:
        for row in rows:
            self._session.add(BacktestTrade(backtest_id=backtest_id, **row))
        await self._session.flush()
