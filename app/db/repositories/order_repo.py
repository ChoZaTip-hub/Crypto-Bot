"""Order repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.order import TradeOrder


class OrderRepository(BaseRepository[TradeOrder]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TradeOrder)

    async def create_order(self, order: dict) -> TradeOrder:
        obj = TradeOrder(**order)
        return await self.create(obj)

    async def update_status(
        self,
        order_id: str,
        status: str,
        exchange_order_id: str | None = None,
    ) -> TradeOrder | None:
        stmt = select(TradeOrder).where(TradeOrder.order_id == order_id)
        result = await self._session.execute(stmt)
        obj = result.scalar_one_or_none()
        if obj is None:
            return None
        obj.status = status
        if exchange_order_id:
            obj.exchange_order_id = exchange_order_id
        await self._session.flush()
        await self._session.refresh(obj)
        return obj

    async def get_by_exchange_id(self, exchange_order_id: str) -> TradeOrder | None:
        stmt = select(TradeOrder).where(TradeOrder.exchange_order_id == exchange_order_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_open_orders(self, symbol: str | None = None) -> list[TradeOrder]:
        stmt = select(TradeOrder).where(
            TradeOrder.status.in_(["pending", "open", "partially_filled"])
        )
        if symbol:
            stmt = stmt.where(TradeOrder.symbol == symbol)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(self, limit: int = 100) -> list[TradeOrder]:
        stmt = select(TradeOrder).order_by(TradeOrder.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
