"""Market analysis / trader briefing tests."""

from app.core.constants import SignalAction
from app.services.market_analysis_service import MarketAnalysisService, _bias_for_tf
from app.strategies.base import StrategyInputs, StrategySignal


def test_bias_for_tf_bullish() -> None:
    bias, _ = _bias_for_tf(
        {"close": 105, "ema": 100, "rsi": 55, "adx": 28, "bb_lower": 95, "bb_upper": 110}
    )
    assert bias == "bullish"


def test_trader_briefing_includes_pnl() -> None:
    svc = MarketAnalysisService()
    inputs = StrategyInputs(
        symbol="BTCUSDT",
        timeframes={
            "5": {"close": 100, "ema": 99, "rsi": 52, "adx": 22},
            "60": {"close": 101, "ema": 98, "rsi": 54, "adx": 26},
        },
        regime="trending",
    )
    signal = StrategySignal(
        symbol="BTCUSDT",
        action=SignalAction.BUY,
        confidence=0.7,
        reason="test",
        entry_price=100,
        stop_loss=98,
        take_profit=106,
        risk_reward_ratio=2.0,
    )
    briefing = svc.build_briefing(inputs, signal)
    assert briefing["trade"]["reward_pct"] == 6.0
    assert briefing["trade"]["risk_pct"] == 2.0
    assert len(briefing["timeframes"]) >= 2
