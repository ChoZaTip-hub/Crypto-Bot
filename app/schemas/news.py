"""News schemas."""

from datetime import datetime

from app.schemas.common import ORMBase


class NewsItemRead(ORMBase):
    id: int
    source: str
    title: str
    url: str | None
    published_at: datetime | None
    created_at: datetime


class SentimentRead(ORMBase):
    id: int
    symbol: str
    score: float
    confidence: float
    label: str
    high_impact: bool
    created_at: datetime
