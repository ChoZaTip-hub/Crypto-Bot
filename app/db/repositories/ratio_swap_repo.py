"""Ratio swap proposal repository."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.ratio_swap_proposal import RatioSwapProposal


class RatioSwapRepository(BaseRepository[RatioSwapProposal]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RatioSwapProposal)

    async def create_proposal(self, data: dict) -> RatioSwapProposal:
        return await self.create(RatioSwapProposal(**data))

    async def get_by_id(self, proposal_id: int) -> RatioSwapProposal | None:
        return await super().get_by_id(proposal_id)

    async def get_pending(self, limit: int = 50) -> list[RatioSwapProposal]:
        stmt = (
            select(RatioSwapProposal)
            .where(RatioSwapProposal.status == "pending")
            .order_by(RatioSwapProposal.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def has_pending_for_pair(self, base_asset: str, quote_asset: str) -> bool:
        stmt = (
            select(RatioSwapProposal)
            .where(
                RatioSwapProposal.status == "pending",
                RatioSwapProposal.base_asset == base_asset,
                RatioSwapProposal.quote_asset == quote_asset,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first() is not None

    async def get_recent(self, limit: int = 30) -> list[RatioSwapProposal]:
        stmt = (
            select(RatioSwapProposal)
            .order_by(RatioSwapProposal.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
