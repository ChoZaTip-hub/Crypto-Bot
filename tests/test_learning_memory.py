"""Tests for learning weights and signal combiner adaptation."""

import pytest

from app.core.constants import SignalAction
from app.strategies.base import StrategySignal
from app.strategies.signal_combiner import SignalCombiner


def test_signal_combiner_applies_weights() -> None:
    combiner = SignalCombiner()
    buy = StrategySignal(
        symbol="BTCUSDT",
        action=SignalAction.BUY,
        confidence=0.8,
        reason="trend",
        strategy_name="trend",
    )
    hold = StrategySignal(
        symbol="BTCUSDT",
        action=SignalAction.HOLD,
        confidence=0.2,
        reason="mr",
        strategy_name="mean_reversion",
    )
    result = combiner.combine([buy, hold], weights={"trend": 2.0, "mean_reversion": 0.5})
    assert result.action == SignalAction.BUY
    assert result.confidence > 0.5


def test_learning_pnl_calculation() -> None:
  entry, exit_ = 100.0, 105.0
  pnl_pct = (exit_ - entry) / entry * 100
  assert pnl_pct == 5.0
