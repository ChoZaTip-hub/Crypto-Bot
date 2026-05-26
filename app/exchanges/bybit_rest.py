"""Bybit V5 REST client wrapper (mainnet only)."""

import asyncio
from typing import Any

from pybit.unified_trading import HTTP

from app.core.config import Settings
from app.core.exceptions import ExchangeError
from app.core.logging import get_logger
from app.exchanges.exchange_types import CandleData

logger = get_logger(__name__)


class BybitRestClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: HTTP | None = None

    def _get_client(self) -> HTTP:
        if self._client is None:
            self._client = HTTP(
                testnet=False,
                api_key=self._settings.bybit_api_key or None,
                api_secret=self._settings.bybit_api_secret or None,
            )
        return self._client

    async def fetch_klines(
        self, symbol: str, interval: str, limit: int = 200
    ) -> list[CandleData]:
        try:
            client = self._get_client()
            resp = client.get_kline(
                category=self._settings.bybit_category,
                symbol=symbol,
                interval=interval,
                limit=limit,
            )
            if resp.get("retCode") != 0:
                raise ExchangeError(
                    f"Bybit kline error: {resp.get('retMsg')}",
                    details={"response": resp},
                )
            rows = resp.get("result", {}).get("list", [])
            candles: list[CandleData] = []
            for row in reversed(rows):
                candles.append(
                    CandleData(
                        symbol=symbol,
                        timeframe=interval,
                        open_time=int(row[0]) // 1000,
                        close_time=int(row[0]) // 1000,
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                        turnover=float(row[6]) if len(row) > 6 else None,
                    )
                )
            return candles
        except ExchangeError:
            raise
        except Exception as exc:
            logger.error("bybit_rest_error", error=str(exc), symbol=symbol)
            raise ExchangeError(str(exc)) from exc

    async def place_order(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            client = self._get_client()
            resp = await asyncio.to_thread(
                client.place_order,
                category=self._settings.bybit_category,
                **params,
            )
            if resp.get("retCode") != 0:
                raise ExchangeError(f"Order failed: {resp.get('retMsg')}", details={"response": resp})
            return resp.get("result", {})
        except ExchangeError:
            raise
        except Exception as exc:
            raise ExchangeError(str(exc)) from exc

    async def get_order(self, symbol: str, order_id: str) -> dict[str, Any]:
        try:
            client = self._get_client()
            resp = await asyncio.to_thread(
                client.get_open_orders,
                category=self._settings.bybit_category,
                symbol=symbol,
                orderId=order_id,
            )
            if resp.get("retCode") != 0:
                resp = await asyncio.to_thread(
                    client.get_order_history,
                    category=self._settings.bybit_category,
                    symbol=symbol,
                    orderId=order_id,
                )
            if resp.get("retCode") != 0:
                raise ExchangeError(f"Get order failed: {resp.get('retMsg')}")
            items = resp.get("result", {}).get("list", [])
            return items[0] if items else {}
        except ExchangeError:
            raise
        except Exception as exc:
            raise ExchangeError(str(exc)) from exc

    async def get_last_price(self, symbol: str) -> float:
        """Latest traded price on Bybit mainnet spot."""
        try:
            client = self._get_client()
            resp = await asyncio.to_thread(
                client.get_tickers,
                category=self._settings.bybit_category,
                symbol=symbol,
            )
            if resp.get("retCode") != 0:
                raise ExchangeError(
                    f"Ticker error: {resp.get('retMsg')}",
                    details={"response": resp},
                )
            items = resp.get("result", {}).get("list", [])
            if not items:
                raise ExchangeError(f"No ticker for {symbol}")
            return float(items[0].get("lastPrice", 0))
        except ExchangeError:
            raise
        except Exception as exc:
            raise ExchangeError(str(exc)) from exc

    async def cancel_order(self, symbol: str, order_id: str) -> None:
        client = self._get_client()
        resp = client.cancel_order(
            category=self._settings.bybit_category,
            symbol=symbol,
            orderId=order_id,
        )
        if resp.get("retCode") != 0:
            raise ExchangeError(f"Cancel failed: {resp.get('retMsg')}")

    async def get_wallet_balance(self) -> dict[str, Any]:
        client = self._get_client()
        return client.get_wallet_balance(accountType="UNIFIED")

    async def list_spot_usdt_symbols(self, *, limit: int = 120) -> list[str]:
        """Tradable USDT spot symbols, preferring liquid names first."""
        try:
            client = self._get_client()
            resp = await asyncio.to_thread(
                client.get_instruments_info,
                category=self._settings.bybit_category,
            )
            if resp.get("retCode") != 0:
                raise ExchangeError(
                    f"Instruments error: {resp.get('retMsg')}",
                    details={"response": resp},
                )
            rows = resp.get("result", {}).get("list", [])
            symbols: list[str] = []
            for row in rows:
                sym = str(row.get("symbol", "")).upper()
                if not sym.endswith("USDT"):
                    continue
                if row.get("status") not in (None, "Trading", "trading"):
                    continue
                quote = str(row.get("quoteCoin", "USDT")).upper()
                if quote != "USDT":
                    continue
                symbols.append(sym)
            symbols = sorted(set(symbols))
            # Keep majors at top for UX
            majors = [
                "BTCUSDT",
                "ETHUSDT",
                "BNBUSDT",
                "SOLUSDT",
                "XRPUSDT",
                "DOGEUSDT",
                "ADAUSDT",
                "AVAXUSDT",
                "LINKUSDT",
                "TONUSDT",
            ]
            ordered = [s for s in majors if s in symbols]
            ordered.extend(s for s in symbols if s not in ordered)
            return ordered[:limit]
        except ExchangeError:
            raise
        except Exception as exc:
            raise ExchangeError(str(exc)) from exc
