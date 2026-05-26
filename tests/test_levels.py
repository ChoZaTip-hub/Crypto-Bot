"""Live trade level helpers."""

from app.core.constants import SignalAction
from app.strategies.base import StrategySignal
from app.strategies.levels import apply_live_trade_levels, compute_sl_tp, pick_atr


def test_compute_sl_tp_buy() -> None:
    sl, tp = compute_sl_tp("BUY", 100_000.0, 500.0)
    assert sl == 99_000.0
    assert tp == 101_500.0


def test_apply_live_trade_levels() -> None:
    sig = StrategySignal(
        symbol="BTCUSDT",
        action=SignalAction.SELL,
        confidence=0.8,
        reason="test",
    )
    tfs = {"5": {"close": 100_000, "atr": 400}}
    apply_live_trade_levels(sig, 75_703.6, tfs)
    assert sig.entry_price == 75_703.6
    assert sig.stop_loss == 76_503.6
    assert sig.take_profit == 74_503.6
    assert pick_atr(tfs) == 400.0
