"""Position schemas."""

from datetime import datetime

from app.schemas.common import ORMBase


class PositionRead(ORMBase):
    id: int
    symbol: str
    side: str
    qty: float
    entry_price: float
    unrealized_pnl: float
    is_open: bool
    opened_at: datetime


class PortfolioSnapshotRead(ORMBase):
    id: int
    equity: float
    cash_balance: float
    unrealized_pnl: float
    open_positions_count: int
    drawdown_pct: float
    created_at: datetime
