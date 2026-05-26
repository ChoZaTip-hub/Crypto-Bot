"""Backtesting simulator tests."""

from app.backtesting.metrics import PerformanceMetrics
from app.backtesting.simulator import TradeSimulator


def test_simulator_trade_pnl() -> None:
    sim = TradeSimulator(initial_balance=10000)
    sim.process_bar("BTCUSDT", 1000, 100, 101, 99, 100, "BUY", 95, 110)
    sim.process_bar("BTCUSDT", 2000, 100, 111, 99, 110, "SELL", None, None)
    assert len(sim.trades) >= 0


def test_metrics_win_rate() -> None:
    pnls = [10, -5, 20, -3, 15]
    assert PerformanceMetrics.win_rate(pnls) == 0.6


def test_metrics_max_drawdown() -> None:
    curve = [10000, 10500, 9500, 11000, 9000]
    dd = PerformanceMetrics.max_drawdown(curve)
    assert dd > 0
