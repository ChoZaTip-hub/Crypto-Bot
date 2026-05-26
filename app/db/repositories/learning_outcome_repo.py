"""Learning outcome repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.learning_outcome import LearningOutcome


class LearningOutcomeRepository(BaseRepository[LearningOutcome]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LearningOutcome)

    async def save_outcome(self, outcome: dict) -> LearningOutcome:
        return await self.create(LearningOutcome(**outcome))

    async def get_recent(self, symbol: str | None = None, limit: int = 50) -> list[LearningOutcome]:
        stmt = select(LearningOutcome).order_by(LearningOutcome.created_at.desc()).limit(limit)
        if symbol:
            stmt = stmt.where(LearningOutcome.symbol == symbol)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_stats_by_regime(self) -> list[tuple[str, str, int, int, float]]:
        """Returns (regime, sub_strategy, wins, losses, avg_pnl)."""
        outcomes = await self.get_recent(limit=500)
        stats: dict[tuple[str, str], list[float]] = {}
        wins: dict[tuple[str, str], int] = {}
        losses: dict[tuple[str, str], int] = {}
        for o in outcomes:
            key = (o.regime, o.sub_strategy)
            stats.setdefault(key, []).append(o.pnl_pct)
            if o.outcome == "win":
                wins[key] = wins.get(key, 0) + 1
            elif o.outcome == "loss":
                losses[key] = losses.get(key, 0) + 1
        result: list[tuple[str, str, int, int, float]] = []
        for key in stats:
            pnls = stats[key]
            result.append(
                (
                    key[0],
                    key[1],
                    wins.get(key, 0),
                    losses.get(key, 0),
                    sum(pnls) / len(pnls) if pnls else 0.0,
                )
            )
        return result
