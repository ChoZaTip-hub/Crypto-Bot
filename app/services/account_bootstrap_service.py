"""Ensure default user + exchange account from .env on startup."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.credentials import encrypt_secret
from app.db.repositories.exchange_account_repo import ExchangeAccountRepository
from app.db.repositories.user_repo import UserRepository
from app.models.exchange_account import ExchangeAccount


class AccountBootstrapService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._accounts = ExchangeAccountRepository(session)

    async def ensure_default_account(self) -> ExchangeAccount:
        user = await self._users.get_or_create_default("default")
        existing = await self._accounts.get_default()
        key = self._settings.bybit_api_key or ""
        secret = self._settings.bybit_api_secret or ""
        if existing:
            if key and not existing.api_key_encrypted:
                existing.api_key_encrypted = encrypt_secret(self._settings, key)
                existing.api_secret_encrypted = encrypt_secret(self._settings, secret)
                existing.trading_mode = self._settings.trading_mode.value
                existing.live_trading_enabled = self._settings.live_trading_enabled
                await self._session.flush()
            return existing

        for acc in await self._accounts.list_all():
            acc.is_default = False

        account = ExchangeAccount(
            user_id=user.id,
            label="default",
            exchange="bybit",
            api_key_encrypted=encrypt_secret(self._settings, key),
            api_secret_encrypted=encrypt_secret(self._settings, secret),
            trading_mode=self._settings.trading_mode.value,
            live_trading_enabled=self._settings.live_trading_enabled,
            copy_enabled=True,
            is_active=True,
            is_default=True,
            order_usdt=self._settings.order_usdt,
            position_size_mode=self._settings.position_size_mode,
            max_open_positions=self._settings.max_open_positions,
            paper_initial_balance=self._settings.paper_initial_balance,
        )
        return await self._accounts.create(account)
