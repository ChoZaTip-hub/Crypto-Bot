"""Mock exchange for paper trading and tests."""

import asyncio
import random
import uuid
from collections.abc import Awaitable, Callable

from app.core.config import get_settings
from app.exchanges.base import ExchangeBase
from app.exchanges.exchange_types import (
    BalanceInfo,
    CandleData,
    ExchangeOrderResult,
    PositionInfo,
    TradeOrderRequest,
)
from app.utils.time import utc_now_ts


class MockExchange(ExchangeBase):
    def __init__(self) -> None:
        self._connected = False
        self._positions: dict[str, PositionInfo] = {}
        settings = get_settings()
        self._balance = settings.paper_initial_balance
        self._prices: dict[str, float] = {
            "BTCUSDT": 65000.0,
            "ETHUSDT": 3500.0,
            "SOLUSDT": 150.0,
            "BNBUSDT": 600.0,
            "XRPUSDT": 0.55,
        }

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    def _base_price(self, symbol: str) -> float:
        return self._prices.get(symbol, 100.0)

    async def fetch_klines(
        self, symbol: str, interval: str, limit: int = 200
    ) -> list[CandleData]:
        base = self._base_price(symbol)
        now = utc_now_ts()
        interval_sec = int(interval) * 60 if interval.isdigit() else 60
        candles: list[CandleData] = []
        for i in range(limit):
            t = now - (limit - i) * interval_sec
            noise = random.uniform(-0.002, 0.002)
            o = base * (1 + noise)
            h = o * (1 + abs(random.uniform(0, 0.003)))
            low = o * (1 - abs(random.uniform(0, 0.003)))
            c = (h + low) / 2
            candles.append(
                CandleData(
                    symbol=symbol,
                    timeframe=interval,
                    open_time=t,
                    close_time=t + interval_sec - 1,
                    open=o,
                    high=h,
                    low=low,
                    close=c,
                    volume=random.uniform(10, 1000),
                )
            )
            base = c
        self._prices[symbol] = candles[-1].close
        return candles

    async def stream_candles(
        self,
        symbol: str,
        interval: str,
        on_candle: Callable[[CandleData], Awaitable[None]],
    ) -> None:
        while self._connected:
            klines = await self.fetch_klines(symbol, interval, limit=1)
            if klines:
                await on_candle(klines[-1])
            await asyncio.sleep(2)

    async def place_order(self, order: TradeOrderRequest) -> ExchangeOrderResult:
        price = self._base_price(order.symbol)
        settings = get_settings()
        slip = settings.paper_slippage_bps / 10_000
        fill_price = price * (1 + slip) if order.side == "Buy" else price * (1 - slip)
        if order.side == "Buy":
            cost = fill_price * order.qty
            self._balance -= cost
            pos = self._positions.get(order.symbol)
            if pos:
                total_qty = pos.qty + order.qty
                pos.entry_price = (pos.entry_price * pos.qty + fill_price * order.qty) / total_qty
                pos.qty = total_qty
            else:
                self._positions[order.symbol] = PositionInfo(
                    symbol=order.symbol,
                    side="Buy",
                    qty=order.qty,
                    entry_price=fill_price,
                )
        else:
            pos = self._positions.get(order.symbol)
            if pos:
                self._balance += fill_price * order.qty
                pos.qty -= order.qty
                if pos.qty <= 0:
                    del self._positions[order.symbol]
        return ExchangeOrderResult(
            exchange_order_id=str(uuid.uuid4()),
            status="filled",
            filled_qty=order.qty,
            avg_price=fill_price,
        )

    async def cancel_order(self, symbol: str, exchange_order_id: str) -> None:
        return

    async def fetch_positions(self) -> list[PositionInfo]:
        return list(self._positions.values())

    async def fetch_balance(self) -> list[BalanceInfo]:
        return [BalanceInfo(coin="USDT", available=self._balance, total=self._balance)]
