"""Application settings loaded from environment."""

from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.constants import (
    BYBIT_CATEGORY_SPOT,
    DEFAULT_SYMBOL_WHITELIST,
    DEFAULT_TIMEFRAMES,
    TradingMode,
)
def _parse_csv_list(v: Any) -> list[str]:
    """Parse comma-separated env values (pydantic-settings does not split lists by default)."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(item).strip() for item in v if str(item).strip()]
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return []
        # Allow JSON arrays in env for compatibility
        if v.startswith("["):
            import json

            parsed = json.loads(v)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [part.strip() for part in v.split(",") if part.strip()]
    raise TypeError(f"Expected str or list, got {type(v)}")


def _parse_symbol_whitelist(v: Any) -> list[str]:
    return [s.upper() for s in _parse_csv_list(v)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "crypto-trading-bot"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    trading_mode: TradingMode = TradingMode.PAPER
    live_trading_enabled: bool = False

    bybit_testnet: bool = True
    bybit_api_key: str = ""
    bybit_api_secret: str = ""
    bybit_category: str = BYBIT_CATEGORY_SPOT

    # SQLite by default for local dev (no Docker). Use Postgres in production.
    database_url: str = "sqlite+aiosqlite:///./data/trading_bot.db"
    redis_url: str = "redis://localhost:6379/0"

    symbol_whitelist: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_SYMBOL_WHITELIST)
    )
    timeframes: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_TIMEFRAMES)
    )

    max_risk_per_trade: float = 0.01
    max_daily_loss: float = 0.03
    max_open_positions: int = 3
    max_exposure_per_symbol: float = 0.15
    mandatory_stop_loss: bool = True
    kill_switch: bool = False
    circuit_breaker_drawdown: float = 0.10
    data_stale_seconds: int = 120
    max_atr_pct: float = 0.05

    paper_initial_balance: float = 10_000.0
    paper_slippage_bps: float = 5.0

    api_admin_token: str = ""
    bot_auto_start: bool = False
    market_poll_interval_seconds: int = 5
    use_bybit_market_data: bool = True

    # 24/7 background: SL/TP position monitor
    background_services_enabled: bool = True
    position_monitor_interval_seconds: int = 10

    # Memory & learning
    memory_enabled: bool = True
    learning_enabled: bool = True

    # Live: attach exchange SL/TP on entry; background monitor closes via market order
    live_place_exchange_sl_tp: bool = True
    live_close_sl_tp_on_exchange: bool = True

    @model_validator(mode="before")
    @classmethod
    def parse_comma_separated_lists(cls, data: Any) -> Any:
        """Convert SYMBOL_WHITELIST=BTC,ETH env strings before list validation."""
        if not isinstance(data, dict):
            return data
        for key, parser in (
            ("symbol_whitelist", _parse_symbol_whitelist),
            ("timeframes", _parse_csv_list),
        ):
            if key in data:
                data[key] = parser(data[key])
        return data

    @field_validator("trading_mode", mode="before")
    @classmethod
    def parse_trading_mode(cls, v: str | TradingMode) -> TradingMode:
        if isinstance(v, TradingMode):
            return v
        return TradingMode(v.lower())

    @property
    def is_live_trading(self) -> bool:
        """Live trading only when mode=live AND explicit flag enabled."""
        return self.trading_mode == TradingMode.LIVE and self.live_trading_enabled

    @property
    def is_paper_trading(self) -> bool:
        return not self.is_live_trading


@lru_cache
def get_settings() -> Settings:
    return Settings()
