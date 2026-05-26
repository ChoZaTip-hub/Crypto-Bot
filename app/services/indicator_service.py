"""Indicator computation service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditEventType
from app.db.repositories.candle_repo import CandleRepository
from app.db.repositories.indicator_repo import IndicatorRepository
from app.indicators import (
    ADXIndicator,
    ATRIndicator,
    BollingerBandsIndicator,
    EMAIndicator,
    MACDIndicator,
    RSIIndicator,
    SMAIndicator,
    VWAPIndicator,
)
from app.services.audit_service import AuditService


class IndicatorService:
    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self._candle_repo = CandleRepository(session)
        self._indicator_repo = IndicatorRepository(session)
        self._audit = audit

    def compute_from_ohlcv(
        self,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        volumes: list[float],
    ) -> dict[str, float | dict[str, float]]:
        if len(closes) < 5:
            return {}
        indicators = {
            "sma": SMAIndicator(20).calculate(closes),
            "ema": EMAIndicator(20).calculate(closes),
            "rsi": RSIIndicator(14).calculate(closes),
            "macd": MACDIndicator().calculate(closes),
            "bollinger": BollingerBandsIndicator().calculate(closes),
            "atr": ATRIndicator().calculate(closes, highs=highs, lows=lows),
            "vwap": VWAPIndicator().calculate(closes, highs=highs, lows=lows, volumes=volumes),
            "adx": ADXIndicator().calculate(closes, highs=highs, lows=lows),
        }
        bb = indicators["bollinger"]
        assert isinstance(bb, dict)
        result: dict[str, float | dict[str, float]] = {
            "close": float(closes[-1]),
            "sma": float(indicators["sma"]),
            "ema": float(indicators["ema"]),
            "rsi": float(indicators["rsi"]),
            "atr": float(indicators["atr"]),
            "vwap": float(indicators["vwap"]),
            "adx": float(indicators["adx"]),
            "bb_upper": float(bb["upper"]),
            "bb_lower": float(bb["lower"]),
            "bb_middle": float(bb["middle"]),
            "bb_width": float(bb["upper"] - bb["lower"]) / float(closes[-1]) if closes[-1] else 0,
        }
        macd = indicators["macd"]
        if isinstance(macd, dict):
            result["macd"] = macd["macd"]
            result["macd_signal"] = macd["signal"]
        return result

    async def compute_for_symbol(
        self, symbol: str, timeframe: str
    ) -> dict[str, float | dict[str, float]]:
        candles = await self._candle_repo.get_by_symbol_and_timeframe(symbol, timeframe)
        if len(candles) < 5:
            return {}
        result = self.compute_from_ohlcv(
            [c.close for c in candles],
            [c.high for c in candles],
            [c.low for c in candles],
            [c.volume for c in candles],
        )
        open_time = candles[-1].open_time
        values_to_save = []
        for name, val in result.items():
            if isinstance(val, (int, float)):
                values_to_save.append(
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "name": name,
                        "open_time": open_time,
                        "value": float(val),
                    }
                )
        if values_to_save:
            await self._indicator_repo.save_values(values_to_save)

        await self._audit.log(
            AuditEventType.INDICATORS_COMPUTED,
            correlation_id=f"{symbol}:{timeframe}",
            payload={"indicators": list(result.keys())},
        )
        return result
