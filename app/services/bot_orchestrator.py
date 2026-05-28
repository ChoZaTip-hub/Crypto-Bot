"""Main bot pipeline coordinator."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_context import DEFAULT_ACCOUNT_ID
from app.core.config import Settings
from app.core.constants import AuditEventType, SignalAction
from app.core.logging import get_logger
from app.exchanges.bybit_client import BybitClient
from app.exchanges.mock_exchange import MockExchange
from app.services.audit_service import AuditService
from app.services.execution_router import ExecutionRouter
from app.services.execution_service import ExecutionService
from app.services.market_data_service import MarketDataService
from app.services.portfolio_service import PortfolioService
from app.services.risk_service import RiskService
from app.services.strategy_service import StrategyService
from app.services.trading_universe_service import TradingUniverseService

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
        self._risk = RiskService(
            session, settings, self._audit, self._market, account_id=DEFAULT_ACCOUNT_ID
        )
        self._execution = ExecutionService(
            session, self._bybit, self._paper, settings, self._audit, account_id=DEFAULT_ACCOUNT_ID
        )
        self._router = ExecutionRouter(session, settings, self._audit, self._market, self._paper)
        self._portfolio = PortfolioService(session, settings, account_id=DEFAULT_ACCOUNT_ID)
        self._universe = TradingUniverseService(session, settings)
        self._paper_connected = False

    @property
    def is_running(self) -> bool:
        return False  # use BotManager for running state

    async def _ensure_paper(self) -> None:
        if not self._paper_connected:
            await self._paper.connect()
            self._paper_connected = True

    async def run_pipeline(self) -> dict[str, Any]:
        """Full cycle: scan universe → ingest → signals → fan-out execution."""
        await self._ensure_paper()
        symbols, scan_snap = await self._universe.resolve()
        if not symbols:
            symbols = list(self._settings.symbol_whitelist)

        market_counts = await self._market.ingest_cycle(symbols)
        await self._session.commit()
        portfolio = await self._portfolio.snapshot()
        results: list[dict[str, Any]] = []

        for symbol in symbols:
            inputs, bundle, _ = await self._strategy.analyze_symbol(symbol)
            if self._settings.ai_influence_trades and self._settings.ai_enabled:
                from app.services.ai.integration import apply_ai_to_signal

                chart_tf = (
                    self._settings.timeframes[0] if self._settings.timeframes else "5"
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

            orders: list[dict] = []
            if signal.action != SignalAction.HOLD and risk.allowed:
                if self._settings.multi_account_copy_enabled:
                    fan = await self._router.execute_for_all_accounts(
                        signal, risk, timeframes=inputs.timeframes
                    )
                    orders = [f for f in fan if f.get("ok")]
                else:
                    single = await self._execution.execute(signal, risk)
                    if single:
                        orders = [{"account_id": DEFAULT_ACCOUNT_ID, "order": single}]
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
                orders=orders,
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
                    "orders": orders,
                    "activity": activity,
                }
            )

        scan_payload: dict[str, Any] | None = None
        if scan_snap:
            scan_payload = {
                "top_symbols": scan_snap.top_symbols,
                "candidates_checked": scan_snap.candidates_checked,
                "ranked": [
                    {
                        "symbol": r.symbol,
                        "score": r.score,
                        "action": r.action,
                        "reason": r.reason[:80],
                    }
                    for r in scan_snap.ranked[:15]
                ],
            }

        return {
            "market_ingested": market_counts,
            "portfolio": portfolio,
            "decisions": results,
            "trading_universe": symbols,
            "scanner": scan_payload,
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
        "scanner_enabled": settings.scanner_enabled,
        "multi_account_copy": settings.multi_account_copy_enabled,
    }


def _cycle_activity_message(
    *,
    symbol: str,
    action: str,
    risk,
    orders: list[dict] | None,
) -> str:
    if action == "HOLD":
        return f"{symbol}: без сделки (HOLD) — нет согласованного сигнала"
    if orders:
        n = len(orders)
        first = orders[0].get("order") or {}
        qty = first.get("qty") or first.get("filled_qty")
        px = first.get("fill_price")
        return (
            f"{symbol}: {action} на {n} счёт(ах) — "
            f"{qty} @ {px}. SL/TP — монитор 24/7"
        )
    if not risk.allowed:
        blocks = ", ".join(risk.blocks) if risk.blocks else "риск"
        return f"{symbol}: {action} не исполнен — {blocks}"
    return f"{symbol}: {action} — ордер не создан"
