"""Combine sub-strategy signals."""

from app.core.constants import SignalAction
from app.strategies.base import StrategySignal


class SignalCombiner:
    def combine(
        self,
        signals: list[StrategySignal],
        weights: dict[str, float] | None = None,
    ) -> StrategySignal:
        weights = weights or {}
        if not signals:
            return StrategySignal(
                symbol="",
                action=SignalAction.HOLD,
                confidence=0.0,
                reason="no_signals",
            )
        def _w(sig: StrategySignal) -> float:
            name = getattr(sig, "strategy_name", "combined") or "combined"
            return weights.get(name, weights.get("combined", 1.0))

        buy_score = sum(_w(s) * s.confidence for s in signals if s.action == SignalAction.BUY)
        sell_score = sum(_w(s) * s.confidence for s in signals if s.action == SignalAction.SELL)
        base = signals[0]
        ml_bias = weights.get("ml_confidence_bias", 0.0)
        if buy_score > sell_score and buy_score >= 0.5:
            action = SignalAction.BUY
            conf = min(1.0, buy_score / max(1, sum(1 for s in signals if s.action == SignalAction.BUY)))
        elif sell_score > buy_score and sell_score >= 0.5:
            action = SignalAction.SELL
            conf = min(1.0, sell_score / max(1, sum(1 for s in signals if s.action == SignalAction.SELL)))
        else:
            action = SignalAction.HOLD
            conf = 0.3
        conf = max(0.0, min(1.0, conf + ml_bias))
        return StrategySignal(
            symbol=base.symbol,
            action=action,
            confidence=conf,
            reason="; ".join(s.reason for s in signals),
            entry_price=base.entry_price,
            stop_loss=base.stop_loss,
            take_profit=base.take_profit,
            risk_reward_ratio=base.risk_reward_ratio,
            correlation_id=base.correlation_id,
            timeframe_confirmations=base.timeframe_confirmations,
            strategy_name=base.strategy_name,
            strategy_version=base.strategy_version,
        )
