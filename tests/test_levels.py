"""Live trade level helpers."""

from app.core.constants import SignalAction
from app.strategies.base import StrategySignal
from app.strategies.levels import (
    SlTpMultipliers,
    apply_live_trade_levels,
    compute_sl_tp,
    estimate_fixed_usdt_pnl,
    pick_atr,
)


def test_compute_sl_tp_buy_default_rr() -> None:
    sl, tp = compute_sl_tp("BUY", 100_000.0, 500.0)
    assert sl == 99_250.0
    assert tp == 102_250.0
    assert abs((tp - 100_000) / (100_000 - sl) - 3.0) < 0.01


def test_min_risk_reward_enforced() -> None:
    m = SlTpMultipliers(sl_atr=2.0, tp_atr=2.5, min_rr=2.0)
    sl, tp = compute_sl_tp("BUY", 100.0, 10.0, mults=m)
    assert sl == 80.0
    assert tp == 140.0


def test_estimate_fixed_usdt_pnl() -> None:
    pnl = estimate_fixed_usdt_pnl(100_000.0, 99_250.0, 102_250.0, 100.0)
    assert pnl["risk_usdt"] == 0.75
    assert pnl["reward_usdt"] == 2.25
    assert pnl["risk_reward_ratio"] == 3.0


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
    assert sig.stop_loss == 76_303.6
    assert sig.take_profit == 73_903.6
    assert pick_atr(tfs) == 400.0


def test_apply_live_trade_levels_with_list_confirmations() -> None:
    sig = StrategySignal(
        symbol="ETHUSDT",
        action=SignalAction.BUY,
        confidence=0.7,
        reason="test",
        timeframe_confirmations=["5", "15", "60"],
    )
    apply_live_trade_levels(sig, 3000.0, {"5": {"close": 3000, "atr": 20}}, horizon_tf="5")
    assert "horizon:5" in sig.timeframe_confirmations
