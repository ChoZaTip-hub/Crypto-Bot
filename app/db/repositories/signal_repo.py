"""Signal repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.signal import Signal


class SignalRepository(BaseRepository[Signal]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Signal)

    async def save_signal(self, signal: dict) -> Signal:
        obj = Signal(**signal)
        return await self.create(obj)

    async def get_latest(self, symbol: str | None = None) -> Signal | None:
        stmt = select(Signal).order_by(Signal.created_at.desc()).limit(1)
        if symbol:
            stmt = stmt.where(Signal.symbol == symbol)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_strategy(self, strategy_name: str, limit: int = 100) -> list[Signal]:
        stmt = (
            select(Signal)
            .where(Signal.strategy_name == strategy_name)
            .order_by(Signal.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_open_signals(self, symbol: str | None = None) -> list[Signal]:
        stmt = select(Signal).where(Signal.action.in_(["BUY", "SELL"]))
        if symbol:
            stmt = stmt.where(Signal.symbol == symbol)
        stmt = stmt.order_by(Signal.created_at.desc()).limit(50)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
