"""RSS feed news provider."""

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser

from app.core.news_sources import RSS_SOURCE_LABELS
from app.news.base import NewsProviderBase
from app.news.types import NewsItemDraft


def _label_for_url(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for key, label in RSS_SOURCE_LABELS.items():
        if key in host:
            return label
    return host or "RSS"


class RssNewsProvider(NewsProviderBase):
    name = "rss"

    def __init__(self, urls: list[str], entries_per_feed: int = 20) -> None:
        self._urls = urls
        self._entries_per_feed = entries_per_feed

    async def fetch(self) -> list[NewsItemDraft]:
        items: list[NewsItemDraft] = []
        for url in self._urls:
            feed = feedparser.parse(url)
            source_label = feed.feed.get("title") or _label_for_url(url)
            # Prefer canonical names for major outlets
            canonical = _label_for_url(url)
            if canonical != urlparse(url).netloc:
                source_label = canonical
            for entry in feed.entries[: self._entries_per_feed]:
                link = entry.get("link") or ""
                title = entry.get("title", "")
                ext_id = hashlib.sha256(f"rss:{link or title}".encode()).hexdigest()
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                items.append(
                    NewsItemDraft(
                        external_id=ext_id,
                        source=f"RSS: {source_label}",
                        title=title,
                        summary=entry.get("summary", ""),
                        url=link or None,
                        published_at=published,
                        provider="rss",
                    )
                )
        return items
