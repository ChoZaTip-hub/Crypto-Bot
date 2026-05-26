"""News repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.news import NewsItem


class NewsRepository(BaseRepository[NewsItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, NewsItem)

    async def upsert_news(self, items: list[dict]) -> None:
        for item in items:
            ext_id = item["external_id"]
            exists = await self.exists(external_id=ext_id)
            if not exists:
                await self.create(NewsItem(**item))

    async def get_recent(self, limit: int = 50) -> list[NewsItem]:
        stmt = select(NewsItem).order_by(NewsItem.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_source(self, source: str, limit: int = 50) -> list[NewsItem]:
        stmt = (
            select(NewsItem)
            .where(NewsItem.source == source)
            .order_by(NewsItem.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_processed(self, news_id: int) -> None:
        obj = await self.get_by_id(news_id)
        if obj:
            obj.processed = True
            await self._session.flush()
