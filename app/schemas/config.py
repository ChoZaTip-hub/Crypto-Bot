"""Bot config schemas."""

from pydantic import BaseModel, Field

from app.core.constants import TradingMode


class BotConfigSchema(BaseModel):
    trading_mode: TradingMode
    live_trading_enabled: bool
    symbol_whitelist: list[str]
    timeframes: list[str]
    max_risk_per_trade: float = Field(ge=0, le=1)
    max_daily_loss: float = Field(ge=0, le=1)
    max_open_positions: int = Field(ge=1)
    kill_switch: bool = False


class BotConfigUpdateSchema(BaseModel):
    kill_switch: bool | None = None
    max_risk_per_trade: float | None = None
    max_open_positions: int | None = None
