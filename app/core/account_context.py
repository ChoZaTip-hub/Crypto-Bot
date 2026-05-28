"""Per-account trading settings overlay (multi-tenant copy trading)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.constants import TradingMode
from app.core.credentials import decrypt_secret
from app.models.exchange_account import ExchangeAccount

DEFAULT_ACCOUNT_ID = 1


@dataclass(frozen=True)
class AccountContext:
    account_id: int
    label: str
    settings: Settings
    copy_enabled: bool
    is_active: bool


def settings_for_account(base: Settings, account: ExchangeAccount) -> Settings:
    """Overlay account keys and sizing onto global Settings."""
    mode = TradingMode(account.trading_mode) if account.trading_mode else base.trading_mode
    live = bool(account.live_trading_enabled)
    updates: dict = {
        "bybit_api_key": decrypt_secret(base, account.api_key_encrypted),
        "bybit_api_secret": decrypt_secret(base, account.api_secret_encrypted),
        "trading_mode": mode,
        "live_trading_enabled": live,
        "order_usdt": float(account.order_usdt or base.order_usdt),
        "position_size_mode": account.position_size_mode or base.position_size_mode,
    }
    if account.max_open_positions is not None:
        updates["max_open_positions"] = int(account.max_open_positions)
    if account.paper_initial_balance is not None:
        updates["paper_initial_balance"] = float(account.paper_initial_balance)
    return base.model_copy(update=updates)


def account_context(base: Settings, account: ExchangeAccount) -> AccountContext:
    return AccountContext(
        account_id=account.id,
        label=account.label,
        settings=settings_for_account(base, account),
        copy_enabled=bool(account.copy_enabled),
        is_active=bool(account.is_active),
    )
