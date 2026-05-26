"""Trend indicators."""

from app.indicators.base import BaseIndicator
from app.utils.math import mean, safe_div


class ADXIndicator(BaseIndicator):
    name = "adx"

    def __init__(self, period: int = 14) -> None:
        self.period = period

    def calculate(self, closes: list[float], **kwargs) -> float:
        highs: list[float] = kwargs.get("highs", closes)
        lows: list[float] = kwargs.get("lows", closes)
        if len(closes) < self.period + 1:
            return 0.0
        plus_dm: list[float] = []
        minus_dm: list[float] = []
        tr_list: list[float] = []
        for i in range(1, min(len(closes), self.period + 1)):
            up = highs[-i] - highs[-i - 1]
            down = lows[-i - 1] - lows[-i]
            plus_dm.append(up if up > down and up > 0 else 0)
            minus_dm.append(down if down > up and down > 0 else 0)
            tr = max(
                highs[-i] - lows[-i],
                abs(highs[-i] - closes[-i - 1]),
                abs(lows[-i] - closes[-i - 1]),
            )
            tr_list.append(tr)
        atr = mean(tr_list) or 1e-10
        plus_di = 100 * mean(plus_dm) / atr
        minus_di = 100 * mean(minus_dm) / atr
        denom = plus_di + minus_di
        return safe_div(100 * abs(plus_di - minus_di), denom, 0.0)
