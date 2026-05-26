"""News ingestion providers."""

from app.news.base import NewsProviderBase
from app.news.bybit_announcements import BybitAnnouncementsProvider
from app.news.crypto_news_api import CryptoNewsApiProvider
from app.news.rss_provider import RssNewsProvider
from app.news.types import NewsItemDraft

__all__ = [
    "NewsProviderBase",
    "NewsItemDraft",
    "RssNewsProvider",
    "BybitAnnouncementsProvider",
    "CryptoNewsApiProvider",
]
