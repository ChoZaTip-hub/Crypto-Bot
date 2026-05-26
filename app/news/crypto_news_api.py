"""Crypto News API aggregator provider.

https://cryptonews-api.com — requires API token.
Fetches headline items for configured tickers and normalizes to NewsItemDraft.
"""

import hashlib
from datetime import datetime, timezone

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.news_sources import PROVIDER_CRYPTO_NEWS_API
from app.news.base import NewsProviderBase
from app.news.types import NewsItemDraft

logger = get_logger(__name__)


class CryptoNewsApiProvider(NewsProviderBase):
    name = PROVIDER_CRYPTO_NEWS_API

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.crypto_news_api_base_url.rstrip("/")
        self._api_key = settings.crypto_news_api_key
        self._items = settings.crypto_news_api_items_per_ticker

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def _tickers_param(self) -> str:
        # API expects BTC, ETH (strip USDT suffix)
        tickers = []
        for sym in self._settings.symbol_whitelist:
            base = sym.replace("USDT", "").replace("USD", "")
            if base:
                tickers.append(base)
        return ",".join(tickers) if tickers else "BTC,ETH"

    async def fetch(self) -> list[NewsItemDraft]:
        if not self.enabled:
            return []

        params = {
            "tickers": self._tickers_param(),
            "items": self._items,
            "page": 1,
            "token": self._api_key,
        }
        items: list[NewsItemDraft] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(self._base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("crypto_news_api_fetch_failed", error=str(exc))
            return []

        # API returns { "data": [ { "title", "news_url", "text", "date", "source_name", ... } ] }
        rows = data.get("data") or data.get("news") or []
        if isinstance(rows, dict):
            rows = rows.get("data", [])

        for row in rows:
            title = row.get("title", "")
            link = row.get("news_url") or row.get("url", "")
            ext_id = hashlib.sha256(f"cna:{link or title}".encode()).hexdigest()
            date_str = row.get("date") or row.get("published_at")
            published = None
            if date_str:
                try:
                    published = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    published = None

            source_name = row.get("source_name") or row.get("source") or "Crypto News API"
            sentiment = row.get("sentiment")
            tags: list[str] = []
            if sentiment:
                tags.append(f"sentiment:{sentiment}")

            items.append(
                NewsItemDraft(
                    external_id=ext_id,
                    source=f"Crypto News API ({source_name})",
                    title=title,
                    summary=row.get("text") or row.get("description", ""),
                    url=link or None,
                    published_at=published,
                    provider=PROVIDER_CRYPTO_NEWS_API,
                    tags=tags,
                )
            )
        return items
