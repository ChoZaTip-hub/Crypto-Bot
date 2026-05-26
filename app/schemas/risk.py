"""Risk schemas."""

from pydantic import BaseModel


class RiskCheckResultSchema(BaseModel):
    allowed: bool
    blocks: list[str]
    risk_score: float
    daily_loss_ok: bool
    data_fresh_ok: bool
    major_news_block: bool
    suggested_qty: float = 0.0


class RiskStatusSchema(BaseModel):
    kill_switch: bool
    circuit_breaker_triggered: bool
    open_positions: int
    daily_pnl_pct: float
    drawdown_pct: float
