"""Order execution service (paper + live)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditEventType, OrderSide, OrderStatus, TradingMode
from app.core.exceptions import LiveTradingDisabledError
from app.core.logging import get_logger
from app.db.repositories.fill_repo import FillRepository
from app.db.repositories.order_repo import OrderRepository
from app.db.repositories.position_repo import PositionRepository
from app.exchanges.base import ExchangeBase
from app.exchanges.exchange_types import TradeOrderRequest
from app.risk.manager import RiskAssessment
from app.services.audit_service import AuditService
from app.strategies.base import StrategySignal
from app.utils.time import utc_now

logger = get_logger(__name__)


class ExecutionService:
    def __init__(
        self,
        session: AsyncSession,
        exchange: ExchangeBase,
        paper_exchange: ExchangeBase,
        settings: Settings,
        audit: AuditService,
    ) -> None:
        self._order_repo = OrderRepository(session)
        self._fill_repo = FillRepository(session)
        self._position_repo = PositionRepository(session)
        self._exchange = exchange
        self._paper = paper_exchange
        self._settings = settings
        self._audit = audit

    def _active_exchange(self) -> ExchangeBase:
        return self._exchange if self._settings.is_live_trading else self._paper

    async def execute(
        self,
        signal: StrategySignal,
        risk: RiskAssessment,
    ) -> dict | None:
        if not risk.allowed or risk.suggested_qty <= 0:
            return None

        if self._settings.trading_mode == TradingMode.LIVE and not self._settings.live_trading_enabled:
            raise LiveTradingDisabledError("Live trading not enabled")

        order_id = str(uuid.uuid4())
        client_order_id = f"{signal.correlation_id[:8]}-{order_id[:8]}"
        side = OrderSide.BUY if signal.action.value == "BUY" else OrderSide.SELL

        order = await self._order_repo.create_order(
            {
                "order_id": order_id,
                "correlation_id": signal.correlation_id,
                "symbol": signal.symbol,
                "side": side.value,
                "qty": risk.suggested_qty,
                "price": signal.entry_price,
                "status": OrderStatus.PENDING.value,
                "trading_mode": self._settings.trading_mode.value,
                "client_order_id": client_order_id,
            }
        )

        ex = self._active_exchange()
        result = await ex.place_order(
            TradeOrderRequest(
                symbol=signal.symbol,
                side=side.value,
                qty=risk.suggested_qty,
                client_order_id=client_order_id,
                correlation_id=signal.correlation_id,
            )
        )

        await self._order_repo.update_status(
            order_id, OrderStatus.FILLED.value, result.exchange_order_id
        )

        fill_id = str(uuid.uuid4())
        await self._fill_repo.save_fill(
            {
                "fill_id": fill_id,
                "order_id": order_id,
                "symbol": signal.symbol,
                "side": side.value,
                "qty": result.filled_qty or risk.suggested_qty,
                "price": result.avg_price or signal.entry_price or 0,
            }
        )

        if side == OrderSide.BUY:
            await self._position_repo.upsert_position(
                {
                    "symbol": signal.symbol,
                    "side": "Buy",
                    "qty": risk.suggested_qty,
                    "entry_price": result.avg_price or signal.entry_price or 0,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "is_open": True,
                    "opened_at": utc_now(),
                    "correlation_id": signal.correlation_id,
                }
            )
        else:
            await self._position_repo.close_position(
                signal.symbol, result.avg_price or signal.entry_price or 0
            )

        await self._audit.log(
            AuditEventType.ORDER_PLACED,
            correlation_id=signal.correlation_id,
            payload={
                "order_id": order_id,
                "mode": self._settings.trading_mode.value,
                "qty": risk.suggested_qty,
            },
        )
        return {"order_id": order_id, "status": "filled"}

    async def close_position_manual(self, symbol: str, qty: float) -> dict | None:
        pos = await self._position_repo.get_by_symbol(symbol)
        if not pos:
            return None
        ex = self._active_exchange()
        result = await ex.place_order(
            TradeOrderRequest(symbol=symbol, side=OrderSide.SELL.value, qty=qty)
        )
        await self._position_repo.close_position(symbol, result.avg_price or 0)
        return {"symbol": symbol, "closed": True}
