"""Multi-asset paper holdings repository."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.asset_holding import AssetHolding


class AssetHoldingRepository(BaseRepository[AssetHolding]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AssetHolding)

    async def get_all(self, trading_mode: str = "paper") -> list[AssetHolding]:
        stmt = select(AssetHolding).where(AssetHolding.trading_mode == trading_mode)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_qty(self, asset: str, trading_mode: str = "paper") -> float:
        stmt = select(AssetHolding).where(
            AssetHolding.asset == asset.upper(),
            AssetHolding.trading_mode == trading_mode,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return float(row.qty) if row else 0.0

    async def set_qty(self, asset: str, qty: float, trading_mode: str = "paper") -> AssetHolding:
        stmt = select(AssetHolding).where(
            AssetHolding.asset == asset.upper(),
            AssetHolding.trading_mode == trading_mode,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.qty = qty
            row.updated_at = datetime.now(timezone.utc)
            await self._session.flush()
            await self._session.refresh(row)
            return row
        return await self.create(
            AssetHolding(
                asset=asset.upper(),
                qty=qty,
                trading_mode=trading_mode,
                updated_at=datetime.now(timezone.utc),
            )
        )
