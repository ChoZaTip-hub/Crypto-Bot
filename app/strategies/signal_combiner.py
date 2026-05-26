"""Combine sub-strategy signals."""

from app.core.constants import SignalAction
from app.strategies.base import StrategySignal


class SignalCombiner:
    def combine(self, signals: list[StrategySignal]) -> StrategySignal:
        if not signals:
            return StrategySignal(
                symbol="",
                action=SignalAction.HOLD,
                confidence=0.0,
                reason="no_signals",
            )
        buys = sum(1 for s in signals if s.action == SignalAction.BUY)
        sells = sum(1 for s in signals if s.action == SignalAction.SELL)
        base = signals[0]
        if buys > sells and buys >= 2:
            action = SignalAction.BUY
            conf = min(1.0, sum(s.confidence for s in signals if s.action == SignalAction.BUY) / buys)
        elif sells > buys and sells >= 2:
            action = SignalAction.SELL
            conf = min(1.0, sum(s.confidence for s in signals if s.action == SignalAction.SELL) / sells)
        else:
            action = SignalAction.HOLD
            conf = 0.3
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
