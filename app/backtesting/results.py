"""Backtest result helpers."""

from dataclasses import dataclass


@dataclass
class BacktestSummary:
    backtest_id: int
    total_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    total_pnl: float
