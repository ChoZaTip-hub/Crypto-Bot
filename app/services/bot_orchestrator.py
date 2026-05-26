"""Main bot pipeline coordinator."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditEventType, SignalAction
from app.core.logging import get_logger
from app.exchanges.bybit_client import BybitClient
from app.exchanges.mock_exchange import MockExchange
from app.services.audit_service import AuditService
from app.services.execution_service import ExecutionService
from app.services.market_data_service import MarketDataService
from app.services.portfolio_service import PortfolioService
from app.services.risk_service import RiskService
from app.services.strategy_service import StrategyService

logger = get_logger(__name__)


class BotOrchestrator:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._audit = AuditService(session)
        self._paper = MockExchange()
        self._bybit = BybitClient(settings)
        self._market_exchange = (
            self._bybit if settings.use_bybit_market_data else self._paper
        )

        from app.db.repositories.candle_repo import CandleRepository

        candle_repo = CandleRepository(session)
        self._market = MarketDataService(
            self._market_exchange, candle_repo, self._audit, settings
        )
        self._strategy = StrategyService(
            session, self._audit, settings.timeframes, settings=settings
        )
        self._risk = RiskService(session, settings, self._audit, self._market)
        self._execution = ExecutionService(
            session, self._bybit, self._paper, settings, self._audit
        )
        self._portfolio = PortfolioService(session, settings)
        self._paper_connected = False

    @property
    def is_running(self) -> bool:
        return False  # use BotManager for running state

    async def _ensure_paper(self) -> None:
        if not self._paper_connected:
            await self._paper.connect()
            self._paper_connected = True

    async def run_pipeline(self) -> dict[str, Any]:
        """Full cycle: market → indicators → signal + explanation → risk → execution."""
        await self._ensure_paper()
        market_counts = await self._market.ingest_cycle()
        portfolio = await self._portfolio.snapshot()
        results: list[dict[str, Any]] = []

        for symbol in self._settings.symbol_whitelist:
            inputs, bundle, _ = await self._strategy.analyze_symbol(symbol)
            if self._settings.ai_influence_trades and self._settings.ai_enabled:
                from app.services.ai.integration import apply_ai_to_signal

                chart_tf = (
                    self._settings.timeframes[0]
                    if self._settings.timeframes
                    else "5"
                )
                bundle.signal = await apply_ai_to_signal(
                    self._settings,
                    inputs,
                    bundle.signal,
                    chart_timeframe=chart_tf,
                )
            risk = await self._risk.evaluate(
                bundle.signal,
                equity=portfolio["equity"],
                daily_pnl_pct=self._portfolio.daily_pnl_pct,
                drawdown_pct=portfolio["drawdown_pct"],
                timeframes=inputs.timeframes,
            )
            signal = await self._strategy.finalize_and_persist(inputs, bundle, risk=risk)

            order = None
            if signal.action != SignalAction.HOLD and risk.allowed:
                order = await self._execution.execute(signal, risk)
            elif signal.action != SignalAction.HOLD and not risk.allowed:
                await self._audit.log(
                    AuditEventType.RISK_BLOCK,
                    correlation_id=signal.correlation_id,
                    payload={
                        "symbol": symbol,
                        "blocks": risk.blocks,
                        "explanation": signal.explanation,
                    },
                )

            briefing = (inputs.memory_context or {}).get("trader_briefing")
            activity = _cycle_activity_message(
                symbol=symbol,
                action=signal.action.value,
                risk=risk,
                order=order,
            )
            results.append(
                {
                    "symbol": symbol,
                    "action": signal.action.value,
                    "confidence": signal.confidence,
                    "reason": signal.reason,
                    "explanation": signal.explanation,
                    "trader_briefing": briefing,
                    "regime": inputs.regime,
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "risk_allowed": risk.allowed,
                    "risk_blocks": risk.blocks,
                    "suggested_qty": risk.suggested_qty,
                    "suggested_usdt": risk.suggested_usdt,
                    "order": order,
                    "activity": activity,
                }
            )

        return {
            "market_ingested": market_counts,
            "portfolio": portfolio,
            "decisions": results,
            "market_source": "bybit" if self._settings.use_bybit_market_data else "mock",
            "trading_params": _trading_params_snapshot(self._settings),
        }


def _trading_params_snapshot(settings: Settings) -> dict:
    return {
        "position_size_mode": settings.position_size_mode,
        "order_usdt": settings.order_usdt,
        "entry_order_type": settings.entry_order_type,
        "max_risk_per_trade": settings.max_risk_per_trade,
        "trading_mode": settings.trading_mode.value,
        "paper_initial_balance": settings.paper_initial_balance,
    }


def _cycle_activity_message(
    *,
    symbol: str,
    action: str,
    risk,
    order: dict | None,
) -> str:
    if action == "HOLD":
        return f"{symbol}: без сделки (HOLD) — нет согласованного сигнала"
    if order:
        qty = order.get("qty") or order.get("filled_qty")
        px = order.get("fill_price")
        usdt = order.get("notional_usdt")
        kind = order.get("order_type", "Market")
        extra = f", ~{usdt:.0f} USDT" if usdt else ""
        return (
            f"{symbol}: {action} исполнен ({kind}) — "
            f"{qty} @ {px}{extra}. Выход по SL/TP — монитор 24/7"
        )
    if not risk.allowed:
        blocks = ", ".join(risk.blocks) if risk.blocks else "риск"
        return f"{symbol}: {action} не исполнен — {blocks}"
    return f"{symbol}: {action} — ордер не создан"

    async def run_once(self) -> dict[str, Any]:
        return await self.run_pipeline()
