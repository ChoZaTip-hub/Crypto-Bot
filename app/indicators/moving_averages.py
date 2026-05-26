"""Moving average indicators."""

from app.indicators.base import BaseIndicator
from app.utils.math import mean


class SMAIndicator(BaseIndicator):
    name = "sma"

    def __init__(self, period: int = 20) -> None:
        self.period = period

    def calculate(self, closes: list[float], **kwargs) -> float:
        if len(closes) < self.period:
            return closes[-1] if closes else 0.0
        return mean(closes[-self.period :])


class EMAIndicator(BaseIndicator):
    name = "ema"

    def __init__(self, period: int = 20) -> None:
        self.period = period

    def calculate(self, closes: list[float], **kwargs) -> float:
        if len(closes) < 2:
            return closes[-1] if closes else 0.0
        alpha = 2 / (self.period + 1)
        ema = closes[0]
        for price in closes[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema
