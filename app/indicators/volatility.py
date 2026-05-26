"""Volatility indicators."""

from app.indicators.base import BaseIndicator
from app.utils.math import mean, std_dev


class BollingerBandsIndicator(BaseIndicator):
    name = "bollinger"

    def __init__(self, period: int = 20, std_dev_mult: float = 2.0) -> None:
        self.period = period
        self.std_dev_mult = std_dev_mult

    def calculate(self, closes: list[float], **kwargs) -> dict[str, float]:
        if len(closes) < self.period:
            mid = closes[-1] if closes else 0.0
            return {"upper": mid, "middle": mid, "lower": mid}
        window = closes[-self.period :]
        mid = mean(window)
        std = std_dev(window)
        return {
            "upper": mid + self.std_dev_mult * std,
            "middle": mid,
            "lower": mid - self.std_dev_mult * std,
        }


class ATRIndicator(BaseIndicator):
    name = "atr"

    def __init__(self, period: int = 14) -> None:
        self.period = period

    def calculate(self, closes: list[float], **kwargs) -> float:
        highs: list[float] = kwargs.get("highs", closes)
        lows: list[float] = kwargs.get("lows", closes)
        if len(closes) < 2:
            return 0.0
        trs = []
        for i in range(1, min(len(closes), self.period + 1)):
            tr = max(
                highs[-i] - lows[-i],
                abs(highs[-i] - closes[-i - 1]),
                abs(lows[-i] - closes[-i - 1]),
            )
            trs.append(tr)
        return mean(trs) if trs else 0.0
