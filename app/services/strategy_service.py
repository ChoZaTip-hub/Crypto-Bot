"""Strategy orchestration service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditEventType, SignalAction
from app.db.repositories.signal_repo import SignalRepository
from app.db.repositories.strategy_decision_repo import StrategyDecisionRepository
from app.risk.manager import RiskAssessment
from app.services.audit_service import AuditService
from app.services.decision_explanation import build_entry_explanation, short_summary
from app.services.live_price_service import fetch_display_price, fetch_live_price
from app.services.market_analysis_service import MarketAnalysisService
from app.services.indicator_service import IndicatorService
from app.services.learning_service import LearningService
from app.services.memory_service import MemoryService
from app.strategies.base import StrategyInputs, StrategySignal
from app.strategies.multi_timeframe_strategy import MultiTimeframeStrategy, StrategyDecisionBundle


class StrategyService:
    def __init__(
        self,
        session: AsyncSession,
        audit: AuditService,
        settings_timeframes: list[str],
        settings: Settings | None = None,
    ) -> None:
        self._indicator = IndicatorService(session, audit)
        self._signal_repo = SignalRepository(session)
        self._decision_repo = StrategyDecisionRepository(session)
        self._audit = audit
        self._strategy = MultiTimeframeStrategy()
        self._timeframes = settings_timeframes
        self._settings = settings
        self._memory = MemoryService(session, audit) if settings and settings.memory_enabled else None
        self._learning = LearningService(session, audit) if settings and settings.learning_enabled else None
        self._analysis = MarketAnalysisService()

    async def analyze_symbol(
        self, symbol: str
    ) -> tuple[StrategyInputs, StrategyDecisionBundle, dict]:
        """Compute indicators and strategy votes without persisting."""
        tf_data: dict[str, dict] = {}
        for tf in self._timeframes:
            indicators = await self._indicator.compute_for_symbol(symbol, tf)
            if indicators:
                tf_data[tf] = indicators

        learning_weights: dict = {}
        live_price: float | None = None
        display: dict = {}
        if self._settings:
            display = await fetch_display_price(symbol, self._settings)
            trading_lp, _ = await fetch_live_price(symbol, self._settings)
            live_price = trading_lp if trading_lp > 0 else float(display.get("price") or 0) or None
        inputs = StrategyInputs(symbol=symbol, timeframes=tf_data, live_price=live_price)
        inputs.regime = self._strategy._detect_regime(inputs)
        if display:
            inputs.memory_context = {
                **inputs.memory_context,
                "display_price": display.get("price"),
            }

        if self._memory:
            await self._memory.capture_symbol(symbol, self._timeframes, regime=inputs.regime)
            inputs.memory_context = await self._memory.get_context(symbol)

        if self._learning:
            learning_weights = await self._learning.get_adjustment(inputs.regime)
            inputs.learning_weights = learning_weights

        bundle = await self._strategy.decide_detailed(inputs)
        display_px = (inputs.memory_context or {}).get("display_price") or inputs.live_price
        briefing = self._analysis.build_briefing(
            inputs, bundle.signal, live_price=display_px
        )
        inputs.memory_context = {**(inputs.memory_context or {}), "trader_briefing": briefing}
        return inputs, bundle, learning_weights

    async def finalize_and_persist(
        self,
        inputs: StrategyInputs,
        bundle: StrategyDecisionBundle,
        risk: RiskAssessment | None = None,
    ) -> StrategySignal:
        """Attach explanation, save signal/decision/audit."""
        signal = bundle.signal
        briefing = (inputs.memory_context or {}).get("trader_briefing")
        if not briefing:
            briefing = self._analysis.build_briefing(inputs, signal, live_price=inputs.live_price)
        briefing_text = self._analysis.format_briefing_text(briefing)
        full_explanation = build_entry_explanation(
            inputs,
            signal,
            bundle.sub_signals,
            active_strategies=bundle.active_strategies,
            risk=risk,
        )
        signal.explanation = f"{briefing_text}\n\n{'─' * 40}\n\n{full_explanation}"
        signal.reason = short_summary(full_explanation)

        signal_id = None
        if signal.action != SignalAction.HOLD:
            saved = await self._signal_repo.save_signal(
                {
                    "correlation_id": signal.correlation_id,
                    "symbol": signal.symbol,
                    "action": signal.action.value,
                    "confidence": signal.confidence,
                    "risk_score": signal.risk_score,
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "risk_reward_ratio": signal.risk_reward_ratio,
                    "reason": signal.reason,
                    "strategy_name": signal.strategy_name,
                    "strategy_version": signal.strategy_version,
                    "timeframe_confirmations": ",".join(signal.timeframe_confirmations),
                }
            )
            signal_id = saved.id

        await self._decision_repo.save_decision(
            {
                "signal_id": signal_id,
                "correlation_id": signal.correlation_id,
                "symbol": inputs.symbol,
                "action": signal.action.value,
                "confidence": signal.confidence,
                "explanation": signal.explanation,
                "regime": inputs.regime,
                "strategy_version": signal.strategy_version,
            }
        )

        await self._audit.log(
            AuditEventType.STRATEGY_DECISION,
            correlation_id=signal.correlation_id,
            payload={
                "symbol": inputs.symbol,
                "action": signal.action.value,
                "confidence": signal.confidence,
                "reason": signal.reason,
                "explanation": signal.explanation,
                "regime": inputs.regime,
                "learning_weights": inputs.learning_weights,
            },
        )
        return signal

    async def generate_signal(
        self,
        symbol: str,
        risk: RiskAssessment | None = None,
    ) -> StrategySignal:
        """One-shot: analyze + explain + persist (used by tests and simple callers)."""
        inputs, bundle, _ = await self.analyze_symbol(symbol)
        return await self.finalize_and_persist(inputs, bundle, risk=risk)
