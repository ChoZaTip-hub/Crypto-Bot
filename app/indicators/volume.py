"""Volume indicators."""

from app.indicators.base import BaseIndicator
from app.utils.math import safe_div


class VWAPIndicator(BaseIndicator):
    name = "vwap"

    def calculate(self, closes: list[float], **kwargs) -> float:
        highs: list[float] = kwargs.get("highs", closes)
        lows: list[float] = kwargs.get("lows", closes)
        volumes: list[float] | None = kwargs.get("volumes")
        if not volumes:
            return closes[-1] if closes else 0.0
        typical = [(h + low + c) / 3 for h, low, c in zip(highs, lows, closes, strict=False)]
        vol_sum = sum(volumes)
        if vol_sum == 0:
            return typical[-1]
        return sum(t * v for t, v in zip(typical, volumes, strict=False)) / vol_sum
