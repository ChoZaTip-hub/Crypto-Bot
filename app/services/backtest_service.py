"""Backtest service facade."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.engine import BacktestEngine
from app.db.repositories.backtest_repo import BacktestRepository
from app.schemas.backtest import BacktestRequestSchema


class BacktestService:
    def __init__(self, session: AsyncSession) -> None:
        self._engine = BacktestEngine(session)
        self._repo = BacktestRepository(session)

    async def run(self, request: BacktestRequestSchema) -> int:
        return await self._engine.run(
            name=request.name,
            symbols=request.symbols,
            timeframes=request.timeframes,
            start_ts=request.start_ts,
            end_ts=request.end_ts,
            strategy_version=request.strategy_version,
        )

    async def get_recent(self, limit: int = 20) -> list:
        return await self._repo.get_recent(limit)

    async def get_by_id(self, backtest_id: int):
        return await self._repo.get_by_id(backtest_id)
