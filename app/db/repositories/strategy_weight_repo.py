"""Strategy weight repository."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.strategy_weight import StrategyWeight


class StrategyWeightRepository(BaseRepository[StrategyWeight]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, StrategyWeight)

    async def get_or_create(self, regime: str, sub_strategy: str) -> StrategyWeight:
        stmt = select(StrategyWeight).where(
            StrategyWeight.regime == regime,
            StrategyWeight.sub_strategy == sub_strategy,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return row
        return await self.create(
            StrategyWeight(regime=regime, sub_strategy=sub_strategy, weight=1.0, ml_bias=0.0)
        )

    async def get_all(self) -> list[StrategyWeight]:
        stmt = select(StrategyWeight).order_by(StrategyWeight.regime, StrategyWeight.sub_strategy)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_from_outcome(
        self, regime: str, sub_strategy: str, pnl_pct: float, outcome: str
    ) -> StrategyWeight:
        row = await self.get_or_create(regime, sub_strategy)
        if outcome == "win":
            row.wins += 1
        elif outcome == "loss":
            row.losses += 1
        row.total_pnl_pct += pnl_pct
        total = row.wins + row.losses
        win_rate = row.wins / total if total else 0.5
        row.weight = max(0.25, min(2.0, 0.5 + win_rate))
        row.ml_bias = max(-0.3, min(0.3, row.ml_bias + pnl_pct * 0.1))
        row.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(row)
        return row
