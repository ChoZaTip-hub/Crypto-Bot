"""News ingestion domain types."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NewsItemDraft:
    """Normalized news item before persistence."""

    external_id: str
    source: str
    title: str
    summary: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    provider: str = "rss"
    category: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_db_dict(self) -> dict:
        summary = self.summary or ""
        if self.tags:
            summary = f"{summary}\n[tags: {', '.join(self.tags)}]".strip()
        if self.category:
            summary = f"{summary}\n[category: {self.category}]".strip()
        if self.provider:
            summary = f"{summary}\n[provider: {self.provider}]".strip()
        return {
            "external_id": self.external_id,
            "source": self.source,
            "title": self.title,
            "summary": summary or None,
            "url": self.url,
            "published_at": self.published_at,
        }
