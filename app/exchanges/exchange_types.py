"""Exchange domain types."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CandleData:
    symbol: str
    timeframe: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "open_time": self.open_time,
            "close_time": self.close_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "turnover": self.turnover,
        }


@dataclass
class TradeOrderRequest:
    symbol: str
    side: str
    qty: float
    order_type: str = "Market"
    price: float | None = None
    client_order_id: str | None = None
    correlation_id: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass
class ExchangeOrderResult:
    exchange_order_id: str
    status: str
    filled_qty: float = 0.0
    avg_price: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class BalanceInfo:
    coin: str
    available: float
    total: float


@dataclass
class PositionInfo:
    symbol: str
    side: str
    qty: float
    entry_price: float
    unrealized_pnl: float = 0.0
