"""Application exceptions."""

from typing import Any


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class RiskLimitExceeded(AppException):
    """Trade blocked by risk rules."""


class ExchangeError(AppException):
    """Exchange API or WebSocket error."""


class DataStaleError(AppException):
    """Market data is too old for trading."""


class LiveTradingDisabledError(AppException):
    """Attempted live trade without LIVE_TRADING_ENABLED."""


class KillSwitchActiveError(AppException):
    """Global kill switch is on."""
