"""Always-on position monitor: SL/TP → real exchange close in live, paper mock otherwise."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.candle_repo import CandleRepository
from app.db.repositories.position_repo import PositionRepository
from app.db.repositories.strategy_decision_repo import StrategyDecisionRepository
from app.exchanges.bybit_client import BybitClient
from app.exchanges.mock_exchange import MockExchange
from app.services.audit_service import AuditService
from app.services.decision_explanation import build_exit_explanation
from app.services.execution_service import ExecutionService
from app.services.learning_service import LearningService

logger = get_logger(__name__)


class PositionMonitorService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._settings = settings
        self._session = session
        self._position_repo = PositionRepository(session)
        self._candle_repo = CandleRepository(session)
        self._decision_repo = StrategyDecisionRepository(session)
        self._audit = AuditService(session)
        self._learning = LearningService(session, self._audit)
        self._bybit = BybitClient(settings)
        self._paper = MockExchange()
        self._execution = ExecutionService(
            session, self._bybit, self._paper, settings, self._audit
        )

    async def _current_price(self, symbol: str) -> float | None:
        if self._settings.is_live_trading:
            try:
                return await self._bybit.fetch_last_price(symbol)
            except Exception as exc:
                logger.warning("live_price_fetch_failed", symbol=symbol, error=str(exc))
        candle = await self._candle_repo.get_latest(symbol, "5")
        if candle is None:
            candle = await self._candle_repo.get_latest(symbol, "1")
        return float(candle.close) if candle else None

    async def tick(self) -> list[dict]:
        """Check open positions; on SL/TP place market close on exchange (live) or paper."""
        closed: list[dict] = []
        positions = await self._position_repo.get_open_positions()

        for pos in positions:
            price = await self._current_price(pos.symbol)
            if price is None:
                continue

            pos.current_price = price
            await self._session.flush()

            exit_reason: str | None = None
            is_long = pos.side.lower() in ("buy", "long")

            if pos.stop_loss is not None:
                if is_long and price <= pos.stop_loss:
                    exit_reason = "stop_loss"
                elif not is_long and price >= pos.stop_loss:
                    exit_reason = "stop_loss"

            if exit_reason is None and pos.take_profit is not None:
                if is_long and price >= pos.take_profit:
                    exit_reason = "take_profit"
                elif not is_long and price <= pos.take_profit:
                    exit_reason = "take_profit"

            if exit_reason is None:
                continue

            entry_note = pos.entry_explanation
            if not entry_note and pos.correlation_id:
                decisions = await self._decision_repo.get_by_correlation_id(pos.correlation_id)
                if decisions:
                    entry_note = decisions[0].explanation

            exit_explanation = build_exit_explanation(
                symbol=pos.symbol,
                side=pos.side,
                entry_price=pos.entry_price,
                exit_price=price,
                exit_reason=exit_reason,
                trigger_price=price,
                stop_loss=pos.stop_loss,
                take_profit=pos.take_profit,
                entry_explanation=entry_note,
            )

            try:
                result = await self._execution.close_position_sl_tp(
                    pos,
                    exit_reason=exit_reason,
                    trigger_price=price,
                    exit_explanation=exit_explanation,
                )
            except Exception as exc:
                logger.error(
                    "position_close_failed",
                    symbol=pos.symbol,
                    reason=exit_reason,
                    error=str(exc),
                )
                closed.append(
                    {
                        "symbol": pos.symbol,
                        "exit_reason": exit_reason,
                        "error": str(exc),
                        "failed": True,
                    }
                )
                continue

            if not result:
                continue

            learning = await self._learning.record_outcome(
                correlation_id=pos.correlation_id,
                symbol=pos.symbol,
                regime="unknown",
                sub_strategy="combined",
                action="BUY" if is_long else "SELL",
                entry_price=pos.entry_price,
                exit_price=result.get("exit_price", price),
                exit_reason=exit_reason,
                features={"exit_explanation": exit_explanation},
            )
            item = {**result, "learning": learning, "explanation": exit_explanation}
            closed.append(item)
            logger.info("position_closed_sl_tp", symbol=pos.symbol, exit_reason=exit_reason)

        return closed
