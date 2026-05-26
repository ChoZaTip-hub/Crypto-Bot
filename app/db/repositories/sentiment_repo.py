"""Sentiment repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.sentiment import SentimentScore


class SentimentRepository(BaseRepository[SentimentScore]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SentimentScore)

    async def save_score(self, score: dict) -> SentimentScore:
        obj = SentimentScore(**score)
        return await self.create(obj)

    async def get_latest(self, symbol: str) -> SentimentScore | None:
        stmt = (
            select(SentimentScore)
            .where(SentimentScore.symbol == symbol)
            .order_by(SentimentScore.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_history(self, symbol: str, limit: int = 200) -> list[SentimentScore]:
        stmt = (
            select(SentimentScore)
            .where(SentimentScore.symbol == symbol)
            .order_by(SentimentScore.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
