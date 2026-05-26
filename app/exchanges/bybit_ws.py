"""Bybit V5 WebSocket client wrapper."""

import asyncio
import json
from collections.abc import Awaitable, Callable

import websockets
from websockets.asyncio.client import ClientConnection

from app.core.config import Settings
from app.core.logging import get_logger
from app.exchanges.exchange_types import CandleData

logger = get_logger(__name__)

PUBLIC_MAINNET = "wss://stream.bybit.com/v5/public/spot"
PUBLIC_TESTNET = "wss://stream-testnet.bybit.com/v5/public/spot"


class BybitWebSocketClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ws: ClientConnection | None = None
        self._running = False

    @property
    def _url(self) -> str:
        return PUBLIC_TESTNET if self._settings.bybit_testnet else PUBLIC_MAINNET

    async def connect(self) -> None:
        self._ws = await websockets.connect(self._url)
        self._running = True
        logger.info("bybit_ws_connected", url=self._url)

    async def close(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def subscribe_kline(
        self,
        symbol: str,
        interval: str,
        on_candle: Callable[[CandleData], Awaitable[None]],
    ) -> None:
        if not self._ws:
            await self.connect()
        topic = f"kline.{interval}.{symbol}"
        sub_msg = {"op": "subscribe", "args": [topic]}
        assert self._ws is not None
        await self._ws.send(json.dumps(sub_msg))
        backoff = 1
        while self._running:
            try:
                assert self._ws is not None
                raw = await asyncio.wait_for(self._ws.recv(), timeout=60)
                data = json.loads(raw)
                if data.get("topic") != topic:
                    continue
                for item in data.get("data", []):
                    candle = CandleData(
                        symbol=symbol,
                        timeframe=interval,
                        open_time=int(item["start"]) // 1000,
                        close_time=int(item["end"]) // 1000,
                        open=float(item["open"]),
                        high=float(item["high"]),
                        low=float(item["low"]),
                        close=float(item["close"]),
                        volume=float(item["volume"]),
                        turnover=float(item.get("turnover", 0)),
                    )
                    await on_candle(candle)
                backoff = 1
            except asyncio.TimeoutError:
                await self._ws.ping()
            except Exception as exc:
                logger.warning("bybit_ws_reconnect", error=str(exc), backoff=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                await self.connect()
                await self._ws.send(json.dumps(sub_msg))
