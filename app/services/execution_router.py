"""Fan-out leader signals to all active exchange accounts."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_context import DEFAULT_ACCOUNT_ID, account_context
from app.core.config import Settings
from app.core.constants import SignalAction
from app.core.logging import get_logger
from app.db.repositories.exchange_account_repo import ExchangeAccountRepository
from app.exchanges.bybit_client import BybitClient
from app.exchanges.mock_exchange import MockExchange
from app.risk.manager import RiskAssessment
from app.services.audit_service import AuditService
from app.services.execution_service import ExecutionService
from app.services.portfolio_service import PortfolioService
from app.services.risk_service import RiskService
from app.services.market_data_service import MarketDataService
from app.strategies.base import StrategySignal

logger = get_logger(__name__)


class ExecutionRouter:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        audit: AuditService,
        market_data: MarketDataService,
        paper: MockExchange,
    ) -> None:
        self._session = session
        self._settings = settings
        self._audit = audit
        self._market_data = market_data
        self._paper = paper
        self._accounts = ExchangeAccountRepository(session)

    async def execute_for_all_accounts(
        self,
        signal: StrategySignal,
        leader_risk: RiskAssessment,
        *,
        timeframes: dict[str, dict] | None = None,
    ) -> list[dict[str, Any]]:
        if signal.action == SignalAction.HOLD or not leader_risk.allowed:
            return []

        accounts = await self._accounts.list_active_copy()
        if not accounts:
            logger.warning("execution_router_no_accounts")
            return []

        results: list[dict[str, Any]] = []
        for acc in accounts:
            ctx = account_context(self._settings, acc)
            if not ctx.copy_enabled or not ctx.is_active:
                continue
            try:
                order = await self._execute_one(
                    signal, ctx.account_id, ctx.settings, timeframes=timeframes
                )
                results.append(
                    {
                        "account_id": ctx.account_id,
                        "label": ctx.label,
                        "order": order,
                        "ok": order is not None,
                    }
                )
            except Exception as exc:
                logger.error(
                    "account_execute_failed",
                    account_id=ctx.account_id,
                    symbol=signal.symbol,
                    error=str(exc),
                )
                results.append(
                    {
                        "account_id": ctx.account_id,
                        "label": ctx.label,
                        "order": None,
                        "ok": False,
                        "error": str(exc),
                    }
                )
        return results

    async def _execute_one(
        self,
        signal: StrategySignal,
        account_id: int,
        acc_settings: Settings,
        *,
        timeframes: dict[str, dict] | None = None,
    ) -> dict | None:
        portfolio = PortfolioService(self._session, acc_settings, account_id=account_id)
        snap = await portfolio.snapshot()
        risk_svc = RiskService(
            self._session, acc_settings, self._audit, self._market_data, account_id=account_id
        )
        risk = await risk_svc.evaluate(
            signal,
            equity=snap["equity"],
            daily_pnl_pct=portfolio.daily_pnl_pct,
            drawdown_pct=snap["drawdown_pct"],
            timeframes=timeframes,
        )
        if not risk.allowed:
            return None

        bybit = BybitClient(acc_settings)
        execution = ExecutionService(
            self._session,
            bybit,
            self._paper,
            acc_settings,
            self._audit,
            account_id=account_id,
        )
        return await execution.execute(signal, risk)
