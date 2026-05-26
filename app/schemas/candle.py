"""Candle schemas."""

from pydantic import BaseModel

from app.schemas.common import ORMBase


class CandleRead(ORMBase):
    id: int
    symbol: str
    timeframe: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketSnapshotSchema(BaseModel):
    symbol: str
    timeframe: str
    last_price: float
    last_candle_ts: int
    indicators: dict[str, float]
