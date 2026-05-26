"""Multi-timeframe strategy orchestrator."""

import uuid
from dataclasses import dataclass, field

from app.core.constants import SignalAction
from app.strategies.base import BaseStrategy, StrategyInputs, StrategySignal
from app.strategies.mean_reversion_strategy import MeanReversionStrategy
from app.strategies.signal_combiner import SignalCombiner
from app.services.market_analysis_service import (
    _bias_for_tf,
    _tf_tier,
    _tf_weight,
    _tier_edge,
)
from app.strategies.trend_strategy import TrendStrategy


@dataclass
class StrategyDecisionBundle:
    signal: StrategySignal
    sub_signals: list[StrategySignal] = field(default_factory=list)
    active_strategies: list[str] = field(default_factory=list)


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

    async def decide_detailed(self, inputs: StrategyInputs) -> StrategyDecisionBundle:
        inputs.regime = self._detect_regime(inputs)
        correlation_id = str(uuid.uuid4())
        sub_signals: list[StrategySignal] = []
        active: list[str] = []

        if inputs.regime == "trending":
            sig = await self._trend.decide(inputs)
            sig.correlation_id = correlation_id
            sub_signals.append(sig)
            active.append("trend")
        elif inputs.regime == "ranging":
            sig = await self._mean_rev.decide(inputs)
            sig.correlation_id = correlation_id
            sub_signals.append(sig)
            active.append("mean_reversion")
        else:
            trend_sig = await self._trend.decide(inputs)
            mr_sig = await self._mean_rev.decide(inputs)
            trend_sig.correlation_id = correlation_id
            mr_sig.correlation_id = correlation_id
            sub_signals.extend([trend_sig, mr_sig])
            active.extend(["trend", "mean_reversion"])

        weights = dict(inputs.learning_weights)
        if inputs.regime == "trending":
            weights.setdefault("trend", weights.get("trend", 1.2))
        elif inputs.regime == "ranging":
            weights.setdefault("mean_reversion", weights.get("mean_reversion", 1.2))

        combined = self._combiner.combine(sub_signals, weights=weights)
        combined.correlation_id = correlation_id
        combined.timeframe_confirmations = list(inputs.timeframes.keys())
        combined.strategy_name = self.name
        combined = self._apply_mtf_confluence(combined, inputs)

        recent_changes = inputs.memory_context.get("recent_changes") or []
        if recent_changes:
            combined.reason += f"; память: {len(recent_changes)} изменений"

        return StrategyDecisionBundle(
            signal=combined,
            sub_signals=sub_signals,
            active_strategies=active,
        )

    def _apply_mtf_confluence(
        self, signal: StrategySignal, inputs: StrategyInputs
    ) -> StrategySignal:
        """Downgrade trades that fight multi-TF bias or lack confidence."""
        from app.core.config import get_settings

        settings = get_settings()
        min_conf = settings.min_signal_confidence
        min_edge = settings.min_mtf_edge

        if signal.action == SignalAction.HOLD:
            return signal

        rows: list[dict] = []
        bull_w = bear_w = 0.0
        for tf, ind in inputs.timeframes.items():
            bias, _ = _bias_for_tf(ind)
            w = _tf_weight(tf)
            rows.append({"tier": _tf_tier(tf), "bias": bias, "weight": w})
            if bias == "bullish":
                bull_w += w
            elif bias == "bearish":
                bear_w += w
        edge = bull_w - bear_w
        h_edge = _tier_edge(rows, "higher")

        if signal.confidence < min_conf:
            signal.action = SignalAction.HOLD
            signal.reason = (
                f"низкая уверенность {signal.confidence * 100:.0f}% < {min_conf * 100:.0f}%"
            )
            return signal

        if signal.action == SignalAction.BUY:
            if h_edge < 0.5:
                signal.action = SignalAction.HOLD
                signal.reason = f"BUY отклонён: старшие ТФ не бычьи (edge={h_edge:.1f})"
            elif edge < min_edge:
                signal.action = SignalAction.HOLD
                signal.reason = f"BUY отклонён: общий консенсус слабый (edge={edge:.1f})"
        elif signal.action == SignalAction.SELL:
            if h_edge > -0.5:
                signal.action = SignalAction.HOLD
                signal.reason = f"SELL отклонён: старшие ТФ не медвежьи (edge={h_edge:.1f})"
            elif edge > -min_edge:
                signal.action = SignalAction.HOLD
                signal.reason = f"SELL отклонён: нет медвежьего консенсуса (edge={edge:.1f})"

        if signal.action != SignalAction.HOLD and inputs.live_price:
            from app.strategies.levels import apply_live_trade_levels

            apply_live_trade_levels(signal, inputs.live_price, inputs.timeframes)
        return signal

    async def decide(self, inputs: StrategyInputs) -> StrategySignal:
        bundle = await self.decide_detailed(inputs)
        return bundle.signal
