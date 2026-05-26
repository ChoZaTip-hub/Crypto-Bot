"""Bybit V5 announcements via official pybit HTTP client.

Example:
    from pybit.unified_trading import HTTP
    session = HTTP(testnet=True)
    session.get_announcement(locale="en-US", limit=1)

Docs: https://bybit-exchange.github.io/docs/v5/announcement
"""

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.news_sources import BYBIT_HIGH_IMPACT_TYPE_KEYS, PROVIDER_BYBIT_ANNOUNCEMENTS
from app.exchanges.bybit_rest import BybitRestClient
from app.news.base import NewsProviderBase
from app.news.types import NewsItemDraft

logger = get_logger(__name__)


def parse_announcement_rows(rows: list[dict[str, Any]]) -> list[NewsItemDraft]:
    """Map Bybit announcement API rows to normalized news drafts."""
    items: list[NewsItemDraft] = []
    for row in rows:
        title = row.get("title", "")
        link = row.get("url", "")
        ext_id = hashlib.sha256(f"bybit:{link or title}".encode()).hexdigest()
        type_obj = row.get("type") or {}
        type_key = type_obj.get("key", "")
        type_title = type_obj.get("title", "")
        tags = list(row.get("tags") or [])
        if type_key in BYBIT_HIGH_IMPACT_TYPE_KEYS and type_title:
            tags.append(type_title)

        ts_ms = (
            row.get("publishTime")
            or row.get("dateTimestamp")
            or row.get("startDateTimestamp")
        )
        published = None
        if ts_ms:
            published = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc)

        items.append(
            NewsItemDraft(
                external_id=ext_id,
                source="Bybit Announcements",
                title=title,
                summary=row.get("description", ""),
                url=link or None,
                published_at=published,
                provider=PROVIDER_BYBIT_ANNOUNCEMENTS,
                category=type_key or None,
                tags=tags,
            )
        )
    return items


class BybitAnnouncementsProvider(NewsProviderBase):
    name = PROVIDER_BYBIT_ANNOUNCEMENTS

    def __init__(self, settings: Settings, rest_client: BybitRestClient | None = None) -> None:
        self._settings = settings
        self._rest = rest_client or BybitRestClient(settings)
        self._locale = settings.bybit_announcements_locale
        self._limit = settings.bybit_announcements_limit

    async def fetch(self) -> list[NewsItemDraft]:
        if not self._settings.bybit_announcements_enabled:
            return []

        try:
            data = await self._rest.get_announcement(
                locale=self._locale,
                limit=self._limit,
            )
        except Exception as exc:
            logger.warning("bybit_announcements_fetch_failed", error=str(exc))
            return []

        if data.get("retCode") != 0:
            logger.warning(
                "bybit_announcements_api_error",
                ret_code=data.get("retCode"),
                ret_msg=data.get("retMsg"),
            )
            return []

        rows = data.get("result", {}).get("list", [])
        logger.info(
            "bybit_announcements_fetched",
            total=data.get("result", {}).get("total"),
            count=len(rows),
        )
        return parse_announcement_rows(rows)
