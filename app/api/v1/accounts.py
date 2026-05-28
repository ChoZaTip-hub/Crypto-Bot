"""Exchange accounts API (multi-tenant copy trading)."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, SettingsDep
from app.core.credentials import encrypt_secret
from app.db.repositories.exchange_account_repo import ExchangeAccountRepository
from app.db.repositories.user_repo import UserRepository
from app.models.exchange_account import ExchangeAccount

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreateBody(BaseModel):
    label: str = "account"
    api_key: str = ""
    api_secret: str = ""
    trading_mode: str = "paper"
    live_trading_enabled: bool = False
    copy_enabled: bool = True
    order_usdt: float = Field(default=100.0, ge=10)
    position_size_mode: str = "fixed_usdt"
    max_open_positions: int | None = None
    paper_initial_balance: float | None = None


@router.get("")
async def list_accounts(session: SessionDep) -> dict:
    repo = ExchangeAccountRepository(session)
    rows = await repo.list_all()
    return {
        "accounts": [
            {
                "id": a.id,
                "label": a.label,
                "trading_mode": a.trading_mode,
                "live_trading_enabled": a.live_trading_enabled,
                "copy_enabled": a.copy_enabled,
                "is_active": a.is_active,
                "is_default": a.is_default,
                "order_usdt": a.order_usdt,
                "has_keys": bool(a.api_key_encrypted),
            }
            for a in rows
        ]
    }


@router.post("")
async def create_account(
    body: AccountCreateBody, session: SessionDep, settings: SettingsDep
) -> dict:
    users = UserRepository(session)
    user = await users.get_or_create_default("default")
    repo = ExchangeAccountRepository(session)
    acc = ExchangeAccount(
        user_id=user.id,
        label=body.label,
        api_key_encrypted=encrypt_secret(settings, body.api_key),
        api_secret_encrypted=encrypt_secret(settings, body.api_secret),
        trading_mode=body.trading_mode,
        live_trading_enabled=body.live_trading_enabled,
        copy_enabled=body.copy_enabled,
        is_active=True,
        is_default=False,
        order_usdt=body.order_usdt,
        position_size_mode=body.position_size_mode,
        max_open_positions=body.max_open_positions,
        paper_initial_balance=body.paper_initial_balance,
    )
    created = await repo.create(acc)
    return {"id": created.id, "label": created.label}


@router.patch("/{account_id}/toggle")
async def toggle_account(
    account_id: int,
    session: SessionDep,
    copy_enabled: bool | None = Query(None),
    is_active: bool | None = Query(None),
) -> dict:
    repo = ExchangeAccountRepository(session)
    acc = await repo.get_by_id(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    if copy_enabled is not None:
        acc.copy_enabled = copy_enabled
    if is_active is not None:
        acc.is_active = is_active
    await session.flush()
    return {"id": acc.id, "copy_enabled": acc.copy_enabled, "is_active": acc.is_active}
