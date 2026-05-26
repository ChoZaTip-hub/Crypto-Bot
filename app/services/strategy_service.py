"""Strategy orchestration service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditEventType, SignalAction
from app.db.repositories.signal_repo import SignalRepository
from app.db.repositories.strategy_decision_repo import StrategyDecisionRepository
from app.services.audit_service import AuditService
from app.services.indicator_service import IndicatorService
from app.services.learning_service import LearningService
from app.services.memory_service import MemoryService
from app.services.sentiment_service import SentimentService
from app.strategies.base import StrategyInputs, StrategySignal
from app.strategies.multi_timeframe_strategy import MultiTimeframeStrategy


class StrategyService:
    def __init__(
        self,
        session: AsyncSession,
        audit: AuditService,
        settings_timeframes: list[str],
        settings: Settings | None = None,
    ) -> None:
        self._indicator = IndicatorService(session, audit)
        self._sentiment = SentimentService(session, audit)
        self._signal_repo = SignalRepository(session)
        self._decision_repo = StrategyDecisionRepository(session)
        self._audit = audit
        self._strategy = MultiTimeframeStrategy()
        self._timeframes = settings_timeframes
        self._settings = settings
        self._memory = MemoryService(session, audit) if settings and settings.memory_enabled else None
        self._learning = LearningService(session, audit) if settings and settings.learning_enabled else None

    async def generate_signal(self, symbol: str) -> StrategySignal:
        tf_data: dict[str, dict] = {}
        for tf in self._timeframes:
            indicators = await self._indicator.compute_for_symbol(symbol, tf)
            if indicators:
                tf_data[tf] = indicators

        sentiment = await self._sentiment.get_latest(symbol)
        memory_context: dict = {}
        learning_weights: dict = {}

        inputs = StrategyInputs(
            symbol=symbol,
            timeframes=tf_data,
            sentiment_score=sentiment.score if sentiment else 0.0,
            sentiment_high_impact=sentiment.high_impact if sentiment else False,
        )
        inputs.regime = self._strategy._detect_regime(inputs)

        if self._memory:
            await self._memory.capture_symbol(symbol, self._timeframes, regime=inputs.regime)
            memory_context = await self._memory.get_context(symbol)
            inputs.memory_context = memory_context

        if self._learning:
            learning_weights = await self._learning.get_adjustment(inputs.regime)
            inputs.learning_weights = learning_weights

        signal = await self._strategy.decide(inputs)

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
            await self._decision_repo.save_decision(
                {
                    "signal_id": saved.id,
                    "correlation_id": signal.correlation_id,
                    "symbol": symbol,
                    "action": signal.action.value,
                    "confidence": signal.confidence,
                    "explanation": signal.reason,
                    "regime": inputs.regime,
                    "strategy_version": signal.strategy_version,
                }
            )
        else:
            await self._decision_repo.save_decision(
                {
                    "signal_id": None,
                    "correlation_id": signal.correlation_id,
                    "symbol": symbol,
                    "action": signal.action.value,
                    "confidence": signal.confidence,
                    "explanation": signal.reason,
                    "regime": inputs.regime,
                    "strategy_version": signal.strategy_version,
                }
            )

        await self._audit.log(
            AuditEventType.STRATEGY_DECISION,
            correlation_id=signal.correlation_id,
            payload={
                "symbol": symbol,
                "action": signal.action.value,
                "confidence": signal.confidence,
                "reason": signal.reason,
                "regime": inputs.regime,
                "learning_weights": learning_weights,
            },
        )
        return signal
