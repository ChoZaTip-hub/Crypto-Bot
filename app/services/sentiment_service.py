"""Deterministic sentiment scoring service."""

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditEventType
from app.db.repositories.news_repo import NewsRepository
from app.db.repositories.sentiment_repo import SentimentRepository
from app.services.audit_service import AuditService

POSITIVE = {"surge", "rally", "approval", "partnership", "adoption", "bullish", "growth"}
NEGATIVE = {"hack", "exploit", "ban", "lawsuit", "crash", "delist", "bearish", "fraud"}
HIGH_IMPACT = {
    "hack",
    "exploit",
    "sec",
    "regulation",
    "ban",
    "delist",
    "delistings",
    "listing",
    "listings",
    "new_crypto",
    "maintenance",
    "etf",
    "fed",
    "rate hike",
    "bybit announcements",
}


class SentimentService:
    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self._news_repo = NewsRepository(session)
        self._sentiment_repo = SentimentRepository(session)
        self._audit = audit

    def score_text(self, text: str) -> tuple[float, float, str, bool, list[str]]:
        lower = text.lower()
        words = set(re.findall(r"[a-z0-9_]+", lower))
        pos = len(words & POSITIVE)
        neg = len(words & NEGATIVE)
        tags = [t for t in HIGH_IMPACT if t in lower]
        # Structured tags from news ingestion: [tags: Spot, Spot Listings]
        if "[tags:" in lower:
            for tag in ("new_crypto", "delistings", "maintenance", "spot listings"):
                if tag in lower:
                    tags.append(tag)
        if "bybit announcements" in lower or "[provider: bybit_announcements]" in lower:
            tags.append("bybit_announcement")
        high_impact = len(tags) > 0
        total = pos + neg
        if total == 0:
            score = 0.0
        else:
            score = (pos - neg) / total
        confidence = min(1.0, (total + len(tags)) / 10)
        label = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"
        return score, confidence, label, high_impact, tags

    async def score_recent_news(self, symbols: list[str]) -> int:
        news_items = await self._news_repo.get_recent(30)
        count = 0
        for item in news_items:
            text = f"{item.title} {item.summary or ''}"
            score, confidence, label, high_impact, tags = self.score_text(text)
            for symbol in symbols:
                sym_base = symbol.replace("USDT", "").lower()
                if sym_base in text.lower() or not symbols:
                    await self._sentiment_repo.save_score(
                        {
                            "symbol": symbol,
                            "score": score,
                            "confidence": confidence,
                            "label": label,
                            "high_impact": high_impact,
                            "event_tags": ",".join(tags) if tags else None,
                            "news_id": item.id,
                        }
                    )
                    count += 1
            await self._news_repo.mark_processed(item.id)
        await self._audit.log(
            AuditEventType.SENTIMENT_SCORED,
            correlation_id="sentiment_batch",
            payload={"scores_saved": count},
        )
        return count

    async def get_latest(self, symbol: str):
        return await self._sentiment_repo.get_latest(symbol)
