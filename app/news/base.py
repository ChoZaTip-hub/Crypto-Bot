"""News provider interface."""

from abc import ABC, abstractmethod

from app.news.types import NewsItemDraft


class NewsProviderBase(ABC):
    """Fetches news from a single upstream source."""

    name: str = "base"

    @abstractmethod
    async def fetch(self) -> list[NewsItemDraft]:
        ...
