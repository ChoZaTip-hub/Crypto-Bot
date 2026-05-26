"""Indicator unit tests."""

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


def test_sma() -> None:
    closes = [float(i) for i in range(1, 31)]
    val = SMAIndicator(10).calculate(closes)
    assert 20.0 <= val <= 30.0


def test_ema() -> None:
    closes = [100 + i * 0.2 for i in range(50)]
    val = EMAIndicator(20).calculate(closes)
    assert 100 <= val <= 115


def test_rsi_bounds() -> None:
    closes = [float(i) for i in range(1, 50)]
    rsi = RSIIndicator(14).calculate(closes)
    assert 0 <= rsi <= 100


def test_macd_returns_dict() -> None:
    closes = [100 + i * 0.4 for i in range(60)]
    result = MACDIndicator().calculate(closes)
    assert "macd" in result
    assert "histogram" in result


def test_bollinger_bands() -> None:
    closes = [100.0] * 30
    bb = BollingerBandsIndicator().calculate(closes)
    assert bb["upper"] >= bb["middle"] >= bb["lower"]


def test_atr_positive() -> None:
    closes = [100 + i * 0.25 for i in range(20)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    atr = ATRIndicator().calculate(closes, highs=highs, lows=lows)
    assert atr >= 0


def test_vwap() -> None:
    closes = [10.0, 11.0, 12.0]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [100.0, 200.0, 300.0]
    vwap = VWAPIndicator().calculate(closes, highs=highs, lows=lows, volumes=volumes)
    assert 10 <= vwap <= 13


def test_adx() -> None:
    closes = [100 + i * 0.67 for i in range(30)]
    adx = ADXIndicator().calculate(closes, highs=[c + 2 for c in closes], lows=[c - 2 for c in closes])
    assert adx >= 0


def test_adx_flat_market_no_division_error() -> None:
    closes = [100.0] * 30
    adx = ADXIndicator().calculate(closes, highs=closes, lows=closes)
    assert adx == 0.0
