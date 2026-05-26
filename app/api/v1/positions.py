"""Position and portfolio endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, SettingsDep
from app.core.security import verify_admin_token
from app.db.repositories.position_repo import PositionRepository
from app.db.repositories.portfolio_repo import PortfolioRepository
from app.schemas.position import PortfolioSnapshotRead, PositionRead
from app.services.execution_service import ExecutionService
from app.services.audit_service import AuditService
from app.exchanges.mock_exchange import MockExchange
from app.exchanges.bybit_client import BybitClient

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=list[PositionRead])
async def list_positions(session: SessionDep) -> list:
    return await PositionRepository(session).get_open_positions()


@router.get("/portfolio", response_model=PortfolioSnapshotRead | None)
async def portfolio_snapshot(session: SessionDep):
    return await PortfolioRepository(session).get_latest()


@router.post("/{symbol}/close", dependencies=[Depends(verify_admin_token)])
async def close_position(symbol: str, session: SessionDep, settings: SettingsDep) -> dict:
    pos = await PositionRepository(session).get_by_symbol(symbol.upper())
    if not pos:
        return {"closed": False, "reason": "no_position"}
    svc = ExecutionService(
        session,
        BybitClient(settings),
        MockExchange(),
        settings,
        AuditService(session),
    )
    result = await svc.close_position_manual(symbol.upper(), pos.qty)
    return result or {"closed": False}
