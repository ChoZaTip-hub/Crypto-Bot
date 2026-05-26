"""Signal schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import SignalAction
from app.schemas.common import ORMBase


class TradeSignalSchema(BaseModel):
    symbol: str
    action: SignalAction
    confidence: float = Field(ge=0, le=1)
    reason: str
    risk_score: float = 0.0
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward_ratio: float | None = None
    correlation_id: str | None = None
    strategy_name: str = "multi_timeframe"
    strategy_version: str = "multi_tf_v1"


class SignalRead(ORMBase):
    id: int
    correlation_id: str
    symbol: str
    action: str
    confidence: float
    risk_score: float
    reason: str
    strategy_name: str
    created_at: datetime
