"""Pair ratio snapshot repository."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.pair_ratio_snapshot import PairRatioSnapshot


class PairRatioRepository(BaseRepository[PairRatioSnapshot]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PairRatioSnapshot)

    async def save_snapshot(self, data: dict) -> PairRatioSnapshot:
        return await self.create(PairRatioSnapshot(**data))

    async def get_history(
        self, base_asset: str, quote_asset: str, limit: int = 500
    ) -> list[PairRatioSnapshot]:
        stmt = (
            select(PairRatioSnapshot)
            .where(
                PairRatioSnapshot.base_asset == base_asset,
                PairRatioSnapshot.quote_asset == quote_asset,
            )
            .order_by(PairRatioSnapshot.sampled_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest(
        self, base_asset: str, quote_asset: str
    ) -> PairRatioSnapshot | None:
        rows = await self.get_history(base_asset, quote_asset, limit=1)
        return rows[0] if rows else None
