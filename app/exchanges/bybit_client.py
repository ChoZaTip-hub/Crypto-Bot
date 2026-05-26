"""Bybit exchange facade (REST + WebSocket)."""

import uuid
from collections.abc import Awaitable, Callable

from app.core.config import Settings, get_settings
from app.core.exceptions import ExchangeError, LiveTradingDisabledError
from app.core.logging import get_logger
from app.exchanges.base import ExchangeBase
from app.exchanges.bybit_rest import BybitRestClient
from app.exchanges.bybit_ws import BybitWebSocketClient
from app.exchanges.exchange_types import (
    BalanceInfo,
    CandleData,
    ExchangeOrderResult,
    PositionInfo,
    TradeOrderRequest,
)

logger = get_logger(__name__)


class BybitClient(ExchangeBase):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._rest = BybitRestClient(self._settings)
        self._ws = BybitWebSocketClient(self._settings)
        self._connected = False

    async def connect(self) -> None:
        await self._ws.connect()
        self._connected = True

    async def close(self) -> None:
        await self._ws.close()
        self._connected = False

    async def fetch_klines(
        self, symbol: str, interval: str, limit: int = 200
    ) -> list[CandleData]:
        return await self._rest.fetch_klines(symbol, interval, limit)

    async def fetch_last_price(self, symbol: str) -> float:
        return await self._rest.get_last_price(symbol)

    async def stream_candles(
        self,
        symbol: str,
        interval: str,
        on_candle: Callable[[CandleData], Awaitable[None]],
    ) -> None:
        await self._ws.subscribe_kline(symbol, interval, on_candle)

    async def place_order(self, order: TradeOrderRequest) -> ExchangeOrderResult:
        if not self._settings.is_live_trading:
            raise LiveTradingDisabledError(
                "Live trading disabled. Set TRADING_MODE=live and LIVE_TRADING_ENABLED=true"
            )
        client_order_id = order.client_order_id or str(uuid.uuid4())
        params = {
            "symbol": order.symbol,
            "side": order.side,
            "orderType": order.order_type,
            "qty": str(order.qty),
            "orderLinkId": client_order_id,
        }
        if order.price:
            params["price"] = str(order.price)
        if order.stop_loss is not None:
            params["stopLoss"] = str(order.stop_loss)
        if order.take_profit is not None:
            params["takeProfit"] = str(order.take_profit)
        if order.stop_loss is not None or order.take_profit is not None:
            params["tpslMode"] = "Full"
        result = await self._rest.place_order(params)
        order_id = result.get("orderId", "")
        avg_price = None
        filled_qty = order.qty
        if order_id:
            try:
                detail = await self._rest.get_order(symbol=order.symbol, order_id=order_id)
                avg_price = float(detail.get("avgPrice") or 0) or None
                filled_qty = float(detail.get("cumExecQty") or order.qty)
            except ExchangeError:
                pass
        return ExchangeOrderResult(
            exchange_order_id=order_id,
            status=result.get("orderStatus", "open"),
            filled_qty=filled_qty,
            avg_price=avg_price,
            raw=result,
        )

    async def cancel_order(self, symbol: str, exchange_order_id: str) -> None:
        await self._rest.cancel_order(symbol, exchange_order_id)

    async def fetch_positions(self) -> list[PositionInfo]:
        return []

    async def fetch_balance(self) -> list[BalanceInfo]:
        try:
            resp = await self._rest.get_wallet_balance()
            balances: list[BalanceInfo] = []
            for acct in resp.get("result", {}).get("list", []):
                for c in acct.get("coin", []):
                    balances.append(
                        BalanceInfo(
                            coin=c.get("coin", ""),
                            available=float(c.get("availableToWithdraw", 0) or 0),
                            total=float(c.get("walletBalance", 0) or 0),
                        )
                    )
            return balances
        except ExchangeError:
            raise
