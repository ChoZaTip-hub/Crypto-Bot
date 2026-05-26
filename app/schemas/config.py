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


class TradingParamsSchema(BaseModel):
    position_size_mode: str = "fixed_usdt"
    order_usdt: float = Field(default=100.0, ge=10, le=1_000_000)
    entry_order_type: str = Field(default="Market", pattern="^(Market|Limit)$")
    max_risk_per_trade: float | None = Field(default=None, ge=0.001, le=0.2)


class TradingParamsUpdateSchema(BaseModel):
    position_size_mode: str | None = None
    order_usdt: float | None = Field(default=None, ge=10, le=1_000_000)
    entry_order_type: str | None = None
    max_risk_per_trade: float | None = Field(default=None, ge=0.001, le=0.2)
