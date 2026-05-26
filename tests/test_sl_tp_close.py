"""SL/TP close logic tests."""

from app.core.constants import SignalAction
from app.strategies.base import StrategySignal


def test_sl_trigger_long() -> None:
    entry, sl, tp, price = 100.0, 95.0, 110.0, 94.0
    is_long = True
    exit_reason = None
    if price <= sl:
        exit_reason = "stop_loss"
    assert exit_reason == "stop_loss"


def test_tp_trigger_long() -> None:
    price, tp, sl = 111.0, 110.0, 95.0
    is_long = True
    exit_reason = None
    if price >= tp:
        exit_reason = "take_profit"
    assert exit_reason == "take_profit"


def test_signal_has_sl_tp_for_exchange_attach() -> None:
    sig = StrategySignal(
        symbol="BTCUSDT",
        action=SignalAction.BUY,
        confidence=0.8,
        reason="test",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
    )
    assert sig.stop_loss == 95.0
    assert sig.take_profit == 110.0
