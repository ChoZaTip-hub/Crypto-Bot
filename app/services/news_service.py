"""Multi-source news ingestion service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditEventType
from app.core.logging import get_logger
from app.db.repositories.news_repo import NewsRepository
from app.news.bybit_announcements import BybitAnnouncementsProvider
from app.news.crypto_news_api import CryptoNewsApiProvider
from app.news.rss_provider import RssNewsProvider
from app.services.audit_service import AuditService

logger = get_logger(__name__)


class NewsService:
    def __init__(
        self,
        session: AsyncSession,
        audit: AuditService,
        settings: Settings,
    ) -> None:
        self._repo = NewsRepository(session)
        self._audit = audit
        self._settings = settings
        self._providers = self._build_providers()

    def _build_providers(self) -> list:
        providers = [
            RssNewsProvider(
                urls=self._settings.news_rss_urls,
                entries_per_feed=self._settings.news_rss_entries_per_feed,
            ),
            BybitAnnouncementsProvider(self._settings),
        ]
        cna = CryptoNewsApiProvider(self._settings)
        if cna.enabled:
            providers.append(cna)
        return providers

    async def ingest_all(self) -> dict[str, int]:
        """Ingest from RSS, Bybit Announcements, and Crypto News API (if configured)."""
        totals: dict[str, int] = {}
        all_items: list[dict] = []

        for provider in self._providers:
            try:
                drafts = await provider.fetch()
                totals[provider.name] = len(drafts)
                all_items.extend(d.to_db_dict() for d in drafts)
            except Exception as exc:
                logger.error("news_provider_failed", provider=provider.name, error=str(exc))
                totals[provider.name] = 0

        if all_items:
            await self._repo.upsert_news(all_items)

        await self._audit.log(
            AuditEventType.NEWS_INGESTED,
            correlation_id="news_batch",
            payload={"counts_by_provider": totals, "total": len(all_items)},
        )
        return totals

    async def ingest_rss(self) -> int:
        """Backward-compatible: ingest all sources."""
        result = await self.ingest_all()
        return sum(result.values())

    async def get_recent(self, limit: int = 50) -> list:
        return await self._repo.get_recent(limit)

    async def get_by_source(self, source: str, limit: int = 50) -> list:
        return await self._repo.get_by_source(source, limit)
