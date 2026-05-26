"""Backtest performance metrics."""

import math
from typing import Sequence


class PerformanceMetrics:
    @staticmethod
    def win_rate(pnls: Sequence[float]) -> float:
        if not pnls:
            return 0.0
        wins = sum(1 for p in pnls if p > 0)
        return wins / len(pnls)

    @staticmethod
    def max_drawdown(equity_curve: Sequence[float]) -> float:
        if not equity_curve:
            return 0.0
        peak = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve:
            peak = max(peak, eq)
            dd = (peak - eq) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        return max_dd

    @staticmethod
    def sharpe_ratio(returns: Sequence[float], risk_free: float = 0.0) -> float:
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(variance) if variance > 0 else 1e-10
        return (mean - risk_free) / std * math.sqrt(252)

    @staticmethod
    def profit_factor(pnls: Sequence[float]) -> float:
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        if gross_loss == 0:
            return gross_profit if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @staticmethod
    def expectancy(pnls: Sequence[float]) -> float:
        if not pnls:
            return 0.0
        return sum(pnls) / len(pnls)
