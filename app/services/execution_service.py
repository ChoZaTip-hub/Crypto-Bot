"""Order execution service (paper + live)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditEventType, OrderSide, OrderStatus, TradingMode
from app.core.exceptions import ExchangeError, LiveTradingDisabledError
from app.core.logging import get_logger
from app.db.repositories.fill_repo import FillRepository
from app.db.repositories.order_repo import OrderRepository
from app.db.repositories.position_repo import PositionRepository
from app.exchanges.base import ExchangeBase
from app.exchanges.exchange_types import TradeOrderRequest
from app.models.position import Position
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
        account_id: int = 1,
    ) -> None:
        self._order_repo = OrderRepository(session)
        self._fill_repo = FillRepository(session)
        self._position_repo = PositionRepository(session)
        self._session = session
        self._exchange = exchange
        self._paper = paper_exchange
        self._settings = settings
        self._audit = audit
        self._account_id = account_id

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

        order_type = self._settings.entry_order_type or "Market"
        limit_price = (
            float(signal.entry_price)
            if order_type == "Limit" and signal.entry_price
            else None
        )

        order = await self._order_repo.create_order(
            {
                "account_id": self._account_id,
                "order_id": order_id,
                "correlation_id": signal.correlation_id,
                "symbol": signal.symbol,
                "side": side.value,
                "order_type": order_type,
                "qty": risk.suggested_qty,
                "price": limit_price,
                "status": OrderStatus.PENDING.value,
                "trading_mode": self._settings.trading_mode.value,
                "client_order_id": client_order_id,
            }
        )

        attach_sl_tp = (
            self._settings.is_live_trading
            and self._settings.live_place_exchange_sl_tp
            and side == OrderSide.BUY
        )

        ex = self._active_exchange()
        try:
            result = await ex.place_order(
                TradeOrderRequest(
                    symbol=signal.symbol,
                    side=side.value,
                    qty=risk.suggested_qty,
                    order_type=order_type,
                    price=limit_price,
                    client_order_id=client_order_id,
                    correlation_id=signal.correlation_id,
                    stop_loss=signal.stop_loss if attach_sl_tp else None,
                    take_profit=signal.take_profit if attach_sl_tp else None,
                )
            )
        except (ExchangeError, LiveTradingDisabledError):
            await self._order_repo.update_status(order_id, OrderStatus.CANCELLED.value, None)
            raise
        except Exception as exc:
            logger.error("order_place_failed", order_id=order_id, error=str(exc))
            await self._order_repo.update_status(order_id, OrderStatus.CANCELLED.value, None)
            raise ExchangeError(str(exc)) from exc

        await self._order_repo.update_status(
            order_id, OrderStatus.FILLED.value, result.exchange_order_id
        )

        fill_id = str(uuid.uuid4())
        fill_price = result.avg_price or signal.entry_price or 0
        await self._fill_repo.save_fill(
            {
                "fill_id": fill_id,
                "order_id": order_id,
                "symbol": signal.symbol,
                "side": side.value,
                "qty": result.filled_qty or risk.suggested_qty,
                "price": fill_price,
            }
        )

        if side == OrderSide.BUY:
            await self._position_repo.upsert_position(
                {
                    "symbol": signal.symbol,
                    "side": "Buy",
                    "qty": result.filled_qty or risk.suggested_qty,
                    "entry_price": fill_price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "is_open": True,
                    "opened_at": utc_now(),
                    "correlation_id": signal.correlation_id,
                    "entry_explanation": signal.explanation or signal.reason,
                },
                account_id=self._account_id,
            )
            await self._audit.log(
                AuditEventType.ORDER_PLACED,
                correlation_id=signal.correlation_id,
                payload={
                    "order_id": order_id,
                    "account_id": self._account_id,
                    "mode": self._settings.trading_mode.value,
                    "qty": risk.suggested_qty,
                    "exchange_sl_tp": attach_sl_tp,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "event": "position_opened",
                    "explanation": signal.explanation or signal.reason,
                },
            )
        else:
            pos = await self._position_repo.get_by_symbol(
                signal.symbol, account_id=self._account_id
            )
            exit_note = signal.explanation or signal.reason
            if pos and exit_note:
                pos.exit_explanation = exit_note
                await self._session.flush()
            await self._position_repo.close_position(
                signal.symbol, fill_price, account_id=self._account_id
            )
            await self._audit.log(
                AuditEventType.ORDER_PLACED,
                correlation_id=signal.correlation_id,
                payload={
                    "order_id": order_id,
                    "account_id": self._account_id,
                    "mode": self._settings.trading_mode.value,
                    "qty": risk.suggested_qty,
                    "event": "position_closed_by_signal",
                    "explanation": exit_note,
                },
            )

        filled_qty = result.filled_qty or risk.suggested_qty
        return {
            "order_id": order_id,
            "status": "filled",
            "exchange_order_id": result.exchange_order_id,
            "exchange_sl_tp": attach_sl_tp,
            "explanation": signal.explanation or signal.reason,
            "order_type": order_type,
            "qty": filled_qty,
            "fill_price": fill_price,
            "notional_usdt": filled_qty * fill_price if fill_price else None,
            "account_id": self._account_id,
        }

    async def close_position_sl_tp(
        self,
        position: Position,
        exit_reason: str,
        trigger_price: float,
        exit_explanation: str | None = None,
    ) -> dict | None:
        """Close open position on exchange (live) or paper mock; record fill + learning hook."""
        if not position.is_open or position.qty <= 0:
            return None

        account_id = int(position.account_id or self._account_id)
        is_long = position.side.lower() in ("buy", "long")
        close_side = OrderSide.SELL if is_long else OrderSide.BUY

        if self._settings.is_live_trading and not self._settings.live_close_sl_tp_on_exchange:
            await self._position_repo.close_position(
                position.symbol, trigger_price, account_id=account_id
            )
            return {"symbol": position.symbol, "closed_in_db_only": True, "exit_reason": exit_reason}

        order_id = str(uuid.uuid4())
        client_order_id = f"sltp-{position.symbol[:4]}-{order_id[:8]}"
        qty = position.qty

        await self._order_repo.create_order(
            {
                "account_id": account_id,
                "order_id": order_id,
                "correlation_id": position.correlation_id or order_id,
                "symbol": position.symbol,
                "side": close_side.value,
                "qty": qty,
                "price": trigger_price,
                "status": OrderStatus.PENDING.value,
                "trading_mode": self._settings.trading_mode.value,
                "client_order_id": client_order_id,
            }
        )

        ex = self._active_exchange()
        try:
            result = await ex.place_order(
                TradeOrderRequest(
                    symbol=position.symbol,
                    side=close_side.value,
                    qty=qty,
                    client_order_id=client_order_id,
                    correlation_id=position.correlation_id,
                )
            )
        except LiveTradingDisabledError:
            await self._order_repo.update_status(order_id, OrderStatus.CANCELLED.value, None)
            raise
        except ExchangeError as exc:
            await self._order_repo.update_status(order_id, OrderStatus.CANCELLED.value, None)
            msg = str(exc).lower()
            if "insufficient" in msg or "not enough" in msg or "balance" in msg:
                logger.warning(
                    "sl_tp_close_already_flat_on_exchange",
                    symbol=position.symbol,
                    reason=exit_reason,
                )
                await self._position_repo.close_position(
                    position.symbol, trigger_price, account_id=account_id
                )
                return {
                    "symbol": position.symbol,
                    "exit_reason": exit_reason,
                    "exit_price": trigger_price,
                    "synced_db_only": True,
                }
            logger.error(
                "sl_tp_close_failed",
                symbol=position.symbol,
                reason=exit_reason,
                error=str(exc),
            )
            raise
        except Exception as exc:
            await self._order_repo.update_status(order_id, OrderStatus.CANCELLED.value, None)
            logger.error(
                "sl_tp_close_failed",
                symbol=position.symbol,
                reason=exit_reason,
                error=str(exc),
            )
            raise

        exit_price = result.avg_price or trigger_price
        await self._order_repo.update_status(
            order_id, OrderStatus.FILLED.value, result.exchange_order_id
        )
        await self._fill_repo.save_fill(
            {
                "fill_id": str(uuid.uuid4()),
                "order_id": order_id,
                "symbol": position.symbol,
                "side": close_side.value,
                "qty": result.filled_qty or qty,
                "price": exit_price,
            }
        )

        if exit_explanation:
            position.exit_explanation = exit_explanation
            await self._session.flush()

        closed = await self._position_repo.close_position(
            position.symbol, exit_price, account_id=account_id
        )
        if closed:
            pnl = (
                (exit_price - position.entry_price) * qty
                if is_long
                else (position.entry_price - exit_price) * qty
            )
            closed.realized_pnl = pnl
            await self._session.flush()

        await self._audit.log(
            AuditEventType.POSITION_SL_TP_CLOSED,
            correlation_id=position.correlation_id or position.symbol,
            payload={
                "symbol": position.symbol,
                "account_id": account_id,
                "exit_reason": exit_reason,
                "exit_price": exit_price,
                "trigger_price": trigger_price,
                "mode": self._settings.trading_mode.value,
                "exchange_order_id": result.exchange_order_id,
                "explanation": exit_explanation,
            },
        )

        return {
            "symbol": position.symbol,
            "exit_reason": exit_reason,
            "exit_price": exit_price,
            "exchange_order_id": result.exchange_order_id,
            "order_id": order_id,
            "explanation": exit_explanation,
            "account_id": account_id,
        }

    async def close_position_manual(
        self, symbol: str, qty: float, account_id: int = 1
    ) -> dict | None:
        pos = await self._position_repo.get_by_symbol(symbol, account_id=account_id)
        if not pos:
            return None
        return await self.close_position_sl_tp(
            pos, "manual", pos.current_price or pos.entry_price
        )
