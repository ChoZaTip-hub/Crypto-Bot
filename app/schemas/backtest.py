"""Backtest schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class BacktestRequestSchema(BaseModel):
    name: str = "default_backtest"
    symbols: list[str]
    timeframes: list[str] = ["5", "60"]
    start_ts: int
    end_ts: int
    strategy_version: str = "multi_tf_v1"
    params: dict[str, float] = Field(default_factory=dict)


class BacktestResultRead(ORMBase):
    id: int
    name: str
    total_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    expectancy: float
    total_pnl: float
    created_at: datetime
