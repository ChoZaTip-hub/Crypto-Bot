"""Mean reversion strategy for ranging markets."""

from app.core.constants import SignalAction
from app.strategies.base import BaseStrategy, StrategyInputs, StrategySignal


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    async def decide(self, inputs: StrategyInputs) -> StrategySignal:
        tf_data = inputs.timeframes.get("5") or {}
        close = tf_data.get("close", 0.0)
        rsi = tf_data.get("rsi", 50.0)
        bb_lower = tf_data.get("bb_lower", close)
        bb_upper = tf_data.get("bb_upper", close)
        atr = tf_data.get("atr", 0.0)

        action = SignalAction.HOLD
        confidence = 0.3
        reason = f"rsi={rsi:.1f}"

        if inputs.regime == "ranging":
            if rsi < 30 and close <= bb_lower:
                action = SignalAction.BUY
                confidence = 0.7
                reason += "; oversold_bb"
            elif rsi > 70 and close >= bb_upper:
                action = SignalAction.SELL
                confidence = 0.7
                reason += "; overbought_bb"

        stop = close - 1.5 * atr if action == SignalAction.BUY else close + 1.5 * atr if action == SignalAction.SELL else None
        tp = close + 2 * atr if action == SignalAction.BUY else close - 2 * atr if action == SignalAction.SELL else None

        return StrategySignal(
            symbol=inputs.symbol,
            action=action,
            confidence=confidence,
            reason=reason,
            risk_score=0.4,
            entry_price=close if action != SignalAction.HOLD else None,
            stop_loss=stop,
            take_profit=tp,
            strategy_name=self.name,
            strategy_version=self.version,
        )
