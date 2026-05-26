"""Momentum indicators."""

from app.indicators.base import BaseIndicator
from app.utils.math import mean


class RSIIndicator(BaseIndicator):
    name = "rsi"

    def __init__(self, period: int = 14) -> None:
        self.period = period

    def calculate(self, closes: list[float], **kwargs) -> float:
        if len(closes) < self.period + 1:
            return 50.0
        deltas = [closes[i] - closes[i - 1] for i in range(-self.period, 0)]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = mean(gains) if gains else 1e-10
        avg_loss = mean(losses) if losses else 1e-10
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))


class MACDIndicator(BaseIndicator):
    name = "macd"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9) -> None:
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def _ema(self, data: list[float], period: int) -> float:
        alpha = 2 / (period + 1)
        ema = data[0]
        for v in data[1:]:
            ema = alpha * v + (1 - alpha) * ema
        return ema

    def calculate(self, closes: list[float], **kwargs) -> dict[str, float]:
        if len(closes) < self.slow:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
        fast_ema = self._ema(closes, self.fast)
        slow_ema = self._ema(closes, self.slow)
        macd_line = fast_ema - slow_ema
        signal_line = macd_line * 0.9
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": macd_line - signal_line,
        }


class StochasticIndicator(BaseIndicator):
    name = "stochastic"

    def __init__(self, period: int = 14) -> None:
        self.period = period

    def calculate(self, closes: list[float], **kwargs) -> dict[str, float]:
        highs: list[float] = kwargs.get("highs", closes)
        lows: list[float] = kwargs.get("lows", closes)
        if len(closes) < self.period:
            return {"k": 50.0, "d": 50.0}
        h = max(highs[-self.period :])
        low = min(lows[-self.period :])
        if h == low:
            return {"k": 50.0, "d": 50.0}
        k = 100 * (closes[-1] - low) / (h - low)
        return {"k": k, "d": k}
