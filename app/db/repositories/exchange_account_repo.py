"""Exchange account repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.exchange_account import ExchangeAccount


class ExchangeAccountRepository(BaseRepository[ExchangeAccount]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ExchangeAccount)

    async def get_by_id(self, account_id: int) -> ExchangeAccount | None:
        return await self.get(account_id)

    async def get_default(self) -> ExchangeAccount | None:
        stmt = select(ExchangeAccount).where(ExchangeAccount.is_default.is_(True)).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active_copy(self) -> list[ExchangeAccount]:
        stmt = (
            select(ExchangeAccount)
            .where(
                ExchangeAccount.is_active.is_(True),
                ExchangeAccount.copy_enabled.is_(True),
            )
            .order_by(ExchangeAccount.id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[ExchangeAccount]:
        stmt = select(ExchangeAccount).order_by(ExchangeAccount.id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
