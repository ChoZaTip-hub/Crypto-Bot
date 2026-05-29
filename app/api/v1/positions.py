"""Position and portfolio endpoints."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, SettingsDep
from app.core.security import verify_admin_token
from app.db.repositories.position_repo import PositionRepository
from app.db.repositories.portfolio_repo import PortfolioRepository
from app.exchanges.bybit_client import BybitClient
from app.exchanges.paper_registry import get_paper_exchange
from app.schemas.position import PortfolioSnapshotRead, PositionRead
from app.services.audit_service import AuditService
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=list[PositionRead])
async def list_positions(
    session: SessionDep,
    account_id: int | None = Query(None),
) -> list:
    return await PositionRepository(session).get_open_positions(account_id)


@router.get("/portfolio", response_model=PortfolioSnapshotRead | None)
async def portfolio_snapshot(session: SessionDep):
    return await PortfolioRepository(session).get_latest()


@router.post("/{symbol}/close", dependencies=[Depends(verify_admin_token)])
async def close_position(
    symbol: str,
    session: SessionDep,
    settings: SettingsDep,
    account_id: int = Query(1),
) -> dict:
    sym = symbol.upper()
    pos = await PositionRepository(session).get_by_symbol(sym, account_id=account_id)
    if not pos:
        return {"closed": False, "reason": "no_position"}
    paper = get_paper_exchange(account_id, initial_balance=settings.paper_initial_balance)
    svc = ExecutionService(
        session,
        BybitClient(settings),
        paper,
        settings,
        AuditService(session),
        account_id=account_id,
    )
    result = await svc.close_position_manual(sym, pos.qty, account_id=account_id)
    return result or {"closed": False}
