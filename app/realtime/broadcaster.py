"""Realtime event broadcaster."""

from app.realtime.channels import BOT_STATUS, FILLS, MARKET, ORDERS, PORTFOLIO, RISK, SIGNALS
from app.realtime.manager import ConnectionManager


class RealtimeBroadcaster:
    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager

    async def market_update(self, data: dict) -> None:
        await self._manager.broadcast({"channel": MARKET, "data": data})

    async def bot_status(self, data: dict) -> None:
        await self._manager.broadcast({"channel": BOT_STATUS, "data": data})

    async def signal(self, data: dict) -> None:
        await self._manager.broadcast({"channel": SIGNALS, "data": data})

    async def risk_alert(self, data: dict) -> None:
        await self._manager.broadcast({"channel": RISK, "data": data})

    async def order_update(self, data: dict) -> None:
        await self._manager.broadcast({"channel": ORDERS, "data": data})

    async def fill_update(self, data: dict) -> None:
        await self._manager.broadcast({"channel": FILLS, "data": data})

    async def portfolio_update(self, data: dict) -> None:
        await self._manager.broadcast({"channel": PORTFOLIO, "data": data})
