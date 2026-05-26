"""Decision explanation builder tests."""

from app.core.constants import SignalAction
from app.risk.manager import MarketContext, PortfolioState, RiskAssessment, RiskManager
from app.services.decision_explanation import build_entry_explanation, build_exit_explanation
from app.strategies.base import StrategyInputs, StrategySignal


def test_build_entry_explanation_buy() -> None:
    inputs = StrategyInputs(
        symbol="BTCUSDT",
        timeframes={"60": {"close": 100.0, "ema": 98.0, "adx": 30.0, "atr": 2.0}},
        regime="trending",
    )
    sub = StrategySignal(
        symbol="BTCUSDT",
        action=SignalAction.BUY,
        confidence=0.8,
        reason="цена выше EMA",
        strategy_name="trend",
    )
    signal = StrategySignal(
        symbol="BTCUSDT",
        action=SignalAction.BUY,
        confidence=0.8,
        reason="combined",
        entry_price=100.0,
        stop_loss=96.0,
        take_profit=106.0,
    )
    text = build_entry_explanation(inputs, signal, [sub], active_strategies=["trend"])
    assert "ПОКУПКА" in text
    assert "Трендовый рынок" in text
    assert "ADX" in text
    assert "Stop Loss" in text


def test_build_exit_explanation_stop_loss() -> None:
    text = build_exit_explanation(
        symbol="BTCUSDT",
        side="Buy",
        entry_price=100.0,
        exit_price=95.0,
        exit_reason="stop_loss",
        trigger_price=95.0,
        stop_loss=95.0,
        take_profit=110.0,
        entry_explanation="тест входа",
    )
    assert "Stop Loss" in text
    assert "тест входа" in text
    assert "-5.00%" in text


def test_explanation_includes_risk_block() -> None:
    settings = __import__("app.core.config", fromlist=["Settings"]).Settings(kill_switch=False)
    rm = RiskManager(settings)
    signal = StrategySignal(
        symbol="BTCUSDT",
        action=SignalAction.BUY,
        confidence=0.9,
        reason="buy",
        entry_price=100.0,
        stop_loss=95.0,
    )
    risk = rm.assess(
        signal,
        MarketContext("BTCUSDT", 0, 0.01, True),
        PortfolioState(10000, 0, 0, 0, 0),
    )
    inputs = StrategyInputs(symbol="BTCUSDT", timeframes={}, regime="unknown")
    text = build_entry_explanation(inputs, signal, [], risk=risk)
    assert "ЗАБЛОКИРОВАНО" in text
    assert "data_stale" in text
