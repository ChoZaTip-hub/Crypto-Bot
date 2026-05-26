"""Backtest endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep
from app.core.security import verify_admin_token
from app.schemas.backtest import BacktestRequestSchema, BacktestResultRead
from app.services.backtest_service import BacktestService

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/run", dependencies=[Depends(verify_admin_token)])
async def run_backtest(
    request: BacktestRequestSchema,
    session: SessionDep,
) -> dict:
    svc = BacktestService(session)
    backtest_id = await svc.run(request)
    return {"backtest_id": backtest_id}


@router.get("", response_model=list[BacktestResultRead])
async def list_backtests(session: SessionDep) -> list:
    return await BacktestService(session).get_recent()


@router.get("/{backtest_id}", response_model=BacktestResultRead)
async def get_backtest(backtest_id: int, session: SessionDep) -> BacktestResultRead:
    result = await BacktestService(session).get_by_id(backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return result
