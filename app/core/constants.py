"""MVP scope constants — single source of truth for defaults."""

from enum import StrEnum

# Bybit market category for MVP
BYBIT_CATEGORY_SPOT: str = "spot"

# Default symbol universe (top liquid spot pairs)
DEFAULT_SYMBOL_WHITELIST: tuple[str, ...] = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
)

# Multi-timeframe analysis (Bybit kline interval codes)
# MVP needs: M1, M5, M15, M30, H1, H4, D1, W1, MN
DEFAULT_TIMEFRAMES: tuple[str, ...] = ("1", "5", "15", "30", "60", "240", "D", "W", "M")

# Strategy versioning
DEFAULT_STRATEGY_VERSION: str = "multi_tf_v1"

# Signal actions
class SignalAction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

# Order sides / statuses
class OrderSide(StrEnum):
    BUY = "Buy"
    SELL = "Sell"

class OrderStatus(StrEnum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class TradingMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"

# Audit event types
class AuditEventType(StrEnum):
    BOT_STARTED = "BOT_STARTED"
    BOT_STOPPED = "BOT_STOPPED"
    MARKET_DATA_RECEIVED = "MARKET_DATA_RECEIVED"
    INDICATORS_COMPUTED = "INDICATORS_COMPUTED"
    STRATEGY_DECISION = "STRATEGY_DECISION"
    RISK_CHECK = "RISK_CHECK"
    RISK_BLOCK = "RISK_BLOCK"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    POSITION_UPDATED = "POSITION_UPDATED"
    NEWS_INGESTED = "NEWS_INGESTED"
    SENTIMENT_SCORED = "SENTIMENT_SCORED"
    BACKTEST_COMPLETED = "BACKTEST_COMPLETED"
    EXCHANGE_ERROR = "EXCHANGE_ERROR"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"

# Risk event levels
class RiskLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
