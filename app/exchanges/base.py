"""Abstract exchange adapter."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from app.exchanges.exchange_types import (
    BalanceInfo,
    CandleData,
    ExchangeOrderResult,
    PositionInfo,
    TradeOrderRequest,
)


class ExchangeBase(ABC):
    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    @abstractmethod
    async def fetch_klines(
        self, symbol: str, interval: str, limit: int = 200
    ) -> list[CandleData]:
        ...

    @abstractmethod
    async def stream_candles(
        self,
        symbol: str,
        interval: str,
        on_candle: Callable[[CandleData], Awaitable[None]],
    ) -> None:
        ...

    @abstractmethod
    async def place_order(self, order: TradeOrderRequest) -> ExchangeOrderResult:
        ...

    @abstractmethod
    async def cancel_order(self, symbol: str, exchange_order_id: str) -> None:
        ...

    @abstractmethod
    async def fetch_positions(self) -> list[PositionInfo]:
        ...

    @abstractmethod
    async def fetch_balance(self) -> list[BalanceInfo]:
        ...
