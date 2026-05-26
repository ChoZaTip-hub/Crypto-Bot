"""Multi-timeframe strategy orchestrator."""

import uuid

from app.core.constants import SignalAction
from app.strategies.base import BaseStrategy, StrategyInputs, StrategySignal
from app.strategies.mean_reversion_strategy import MeanReversionStrategy
from app.strategies.signal_combiner import SignalCombiner
from app.strategies.trend_strategy import TrendStrategy


class MultiTimeframeStrategy(BaseStrategy):
    name = "multi_timeframe"

    def __init__(self) -> None:
        self._trend = TrendStrategy()
        self._mean_rev = MeanReversionStrategy()
        self._combiner = SignalCombiner()

    def _detect_regime(self, inputs: StrategyInputs) -> str:
        tf60 = inputs.timeframes.get("60", {})
        adx = tf60.get("adx", 0.0)
        bb_width = tf60.get("bb_width", 0.0)
        if adx > 25:
            return "trending"
        if adx < 20 and bb_width < 0.02:
            return "ranging"
        return "unknown"

    async def decide(self, inputs: StrategyInputs) -> StrategySignal:
        inputs.regime = self._detect_regime(inputs)
        correlation_id = str(uuid.uuid4())
        sub_signals: list[StrategySignal] = []

        if inputs.regime == "trending":
            sig = await self._trend.decide(inputs)
            sig.correlation_id = correlation_id
            sub_signals.append(sig)
        elif inputs.regime == "ranging":
            sig = await self._mean_rev.decide(inputs)
            sig.correlation_id = correlation_id
            sub_signals.append(sig)
        else:
            trend_sig = await self._trend.decide(inputs)
            mr_sig = await self._mean_rev.decide(inputs)
            trend_sig.correlation_id = correlation_id
            mr_sig.correlation_id = correlation_id
            sub_signals.extend([trend_sig, mr_sig])

        weights = dict(inputs.learning_weights)
        if inputs.regime == "trending":
            weights.setdefault("trend", weights.get("trend", 1.2))
        elif inputs.regime == "ranging":
            weights.setdefault("mean_reversion", weights.get("mean_reversion", 1.2))

        combined = self._combiner.combine(sub_signals, weights=weights)
        combined.correlation_id = correlation_id
        combined.timeframe_confirmations = list(inputs.timeframes.keys())

        recent_changes = inputs.memory_context.get("recent_changes") or []
        if recent_changes:
            combined.reason += f"; memory_events={len(recent_changes)}"

        if inputs.sentiment_high_impact:
            combined.action = SignalAction.HOLD
            combined.reason += "; blocked_by_high_impact_sentiment"
            combined.confidence *= 0.5

        return combined
