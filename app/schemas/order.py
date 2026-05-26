"""Order schemas."""

from datetime import datetime

from app.schemas.common import ORMBase


class OrderRead(ORMBase):
    id: int
    order_id: str
    symbol: str
    side: str
    qty: float
    status: str
    trading_mode: str
    correlation_id: str
    created_at: datetime


class FillRead(ORMBase):
    id: int
    fill_id: str
    order_id: str
    symbol: str
    side: str
    qty: float
    price: float
    created_at: datetime
