"""Trend-following strategy."""

from app.core.constants import SignalAction
from app.strategies.base import BaseStrategy, StrategyInputs, StrategySignal


class TrendStrategy(BaseStrategy):
    name = "trend"

    async def decide(self, inputs: StrategyInputs) -> StrategySignal:
        tf_data = inputs.timeframes.get("60") or inputs.timeframes.get("5") or {}
        close = tf_data.get("close", 0.0)
        ema = tf_data.get("ema", close)
        adx = tf_data.get("adx", 0.0)
        atr = tf_data.get("atr", 0.0)

        action = SignalAction.HOLD
        confidence = 0.3
        reason_parts = [f"regime={inputs.regime}", f"adx={adx:.1f}"]

        if adx > 25 and close > ema:
            action = SignalAction.BUY
            confidence = min(0.85, 0.5 + adx / 100)
            reason_parts.append("uptrend_ema")
        elif adx > 25 and close < ema:
            action = SignalAction.SELL
            confidence = min(0.85, 0.5 + adx / 100)
            reason_parts.append("downtrend_ema")

        stop = close - 2 * atr if action == SignalAction.BUY else close + 2 * atr if action == SignalAction.SELL else None
        tp = close + 3 * atr if action == SignalAction.BUY else close - 3 * atr if action == SignalAction.SELL else None
        rr = 1.5 if stop and tp else None

        return StrategySignal(
            symbol=inputs.symbol,
            action=action,
            confidence=confidence,
            reason="; ".join(reason_parts),
            risk_score=0.3 if action == SignalAction.HOLD else 0.5,
            entry_price=close if action != SignalAction.HOLD else None,
            stop_loss=stop,
            take_profit=tp,
            risk_reward_ratio=rr,
            strategy_name=self.name,
            strategy_version=self.version,
        )
