"""Risk service wrapper."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditEventType, RiskLevel
from app.db.repositories.position_repo import PositionRepository
from app.db.repositories.risk_repo import RiskRepository
from app.risk.manager import MarketContext, PortfolioState, RiskAssessment, RiskManager
from app.services.audit_service import AuditService
from app.services.market_data_service import MarketDataService
from app.strategies.base import StrategySignal
from app.utils.serialization import dumps_json


class RiskService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        audit: AuditService,
        market_data: MarketDataService,
    ) -> None:
        self._manager = RiskManager(settings)
        self._position_repo = PositionRepository(session)
        self._risk_repo = RiskRepository(session)
        self._audit = audit
        self._market_data = market_data
        self._settings = settings

    async def evaluate(
        self,
        signal: StrategySignal,
        equity: float,
        daily_pnl_pct: float,
        drawdown_pct: float,
        primary_timeframe: str = "5",
    ) -> RiskAssessment:
        positions = await self._position_repo.get_open_positions()
        open_for_symbol = next((p for p in positions if p.symbol == signal.symbol), None)
        symbol_exposure = 0.0
        if equity > 0:
            for p in positions:
                if p.symbol == signal.symbol:
                    symbol_exposure = ((p.current_price or p.entry_price) * p.qty) / equity

        market = MarketContext(
            symbol=signal.symbol,
            last_candle_ts=self._market_data.get_last_ts(signal.symbol, primary_timeframe),
            atr_pct=signal.risk_score,
            data_stale=self._market_data.is_data_stale(signal.symbol, primary_timeframe),
        )
        portfolio = PortfolioState(
            equity=equity,
            daily_pnl_pct=daily_pnl_pct,
            drawdown_pct=drawdown_pct,
            open_positions_count=len(positions),
            symbol_exposure_pct=symbol_exposure,
        )
        assessment = self._manager.assess(signal, market, portfolio)

        if signal.action.value == "BUY" and open_for_symbol:
            assessment.allowed = False
            assessment.blocks.append("position_already_open")
        elif signal.action.value == "SELL":
            if open_for_symbol:
                assessment.suggested_qty = open_for_symbol.qty
                assessment.allowed = True
                assessment.blocks = [b for b in assessment.blocks if b != "max_open_positions"]
            else:
                assessment.allowed = False
                assessment.blocks.append("no_position_to_close")

        if not assessment.allowed and signal.action.value != "HOLD":
            await self._risk_repo.save_event(
                {
                    "correlation_id": signal.correlation_id,
                    "level": RiskLevel.WARNING.value,
                    "event_type": "trade_blocked",
                    "message": "; ".join(assessment.blocks),
                    "symbol": signal.symbol,
                    "payload_json": dumps_json({"blocks": assessment.blocks}),
                }
            )
            await self._audit.log(
                AuditEventType.RISK_BLOCK,
                correlation_id=signal.correlation_id,
                payload={"blocks": assessment.blocks},
            )
        else:
            await self._audit.log(
                AuditEventType.RISK_CHECK,
                correlation_id=signal.correlation_id,
                payload={"allowed": assessment.allowed, "qty": assessment.suggested_qty},
            )
        return assessment
