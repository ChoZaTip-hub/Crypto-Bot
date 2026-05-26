"""News ingestion worker."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.audit_service import AuditService
from app.services.news_service import NewsService
from app.services.sentiment_service import SentimentService


class NewsWorker:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._news = NewsService(session, AuditService(session), settings)
        self._sentiment = SentimentService(session, AuditService(session))
        self._settings = settings
        self._running = False

    async def start(self, interval: int = 300) -> None:
        self._running = True
        while self._running:
            await self._news.ingest_rss()
            await self._sentiment.score_recent_news(self._settings.symbol_whitelist)
            await asyncio.sleep(interval)

    def stop(self) -> None:
        self._running = False
