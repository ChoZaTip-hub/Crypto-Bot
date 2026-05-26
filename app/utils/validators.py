"""Validation helpers."""

from app.core.config import get_settings


def is_symbol_allowed(symbol: str) -> bool:
    settings = get_settings()
    return symbol.upper() in settings.symbol_whitelist


def normalize_symbol(symbol: str) -> str:
    return symbol.upper().replace("/", "").replace("-", "")
