"""Candlestick pattern detection."""

from app.indicators.base import BaseIndicator


class PatternDetector(BaseIndicator):
    name = "patterns"

    def calculate(self, closes: list[float], **kwargs) -> dict[str, bool]:
        opens: list[float] = kwargs.get("opens", closes)
        if len(closes) < 2:
            return {"bullish_engulfing": False, "bearish_engulfing": False}
        o1, c1 = opens[-2], closes[-2]
        o2, c2 = opens[-1], closes[-1]
        bullish = c1 < o1 and c2 > o2 and c2 > o1 and o2 < c1
        bearish = c1 > o1 and c2 < o2 and c2 < o1 and o2 > c1
        return {"bullish_engulfing": bullish, "bearish_engulfing": bearish}
