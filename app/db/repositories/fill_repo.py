"""Fill repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.fill import Fill


class FillRepository(BaseRepository[Fill]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Fill)

    async def save_fill(self, fill: dict) -> Fill:
        obj = Fill(**fill)
        return await self.create(obj)

    async def bulk_save(self, fills: list[dict]) -> None:
        for f in fills:
            self._session.add(Fill(**f))
        await self._session.flush()

    async def get_by_order_id(self, order_id: str) -> list[Fill]:
        stmt = select(Fill).where(Fill.order_id == order_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
