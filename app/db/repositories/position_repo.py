"""Position repository."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.position import Position


class PositionRepository(BaseRepository[Position]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Position)

    async def get_open_positions(self) -> list[Position]:
        stmt = select(Position).where(Position.is_open.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_symbol(self, symbol: str) -> Position | None:
        stmt = select(Position).where(Position.symbol == symbol, Position.is_open.is_(True))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_position(self, position: dict) -> Position:
        symbol = position["symbol"]
        existing = await self.get_by_symbol(symbol)
        if existing:
            for k, v in position.items():
                if k != "symbol":
                    setattr(existing, k, v)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        obj = Position(**position)
        return await self.create(obj)

    async def close_position(
        self, symbol: str, close_price: float, closed_at: int | None = None
    ) -> Position | None:
        pos = await self.get_by_symbol(symbol)
        if pos is None:
            return None
        pos.is_open = False
        pos.current_price = close_price
        pos.closed_at = datetime.fromtimestamp(
            (closed_at or int(datetime.now(timezone.utc).timestamp())),
            tz=timezone.utc,
        )
        await self._session.flush()
        await self._session.refresh(pos)
        return pos

    async def update_pnl(
        self, symbol: str, unrealized_pnl: float, realized_pnl: float
    ) -> Position | None:
        pos = await self.get_by_symbol(symbol)
        if pos is None:
            return None
        pos.unrealized_pnl = unrealized_pnl
        pos.realized_pnl = realized_pnl
        await self._session.flush()
        await self._session.refresh(pos)
        return pos
