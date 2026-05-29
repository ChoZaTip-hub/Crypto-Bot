"""Risk endpoints."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep
from app.db.repositories.portfolio_repo import PortfolioRepository
from app.db.repositories.position_repo import PositionRepository
from app.db.repositories.risk_repo import RiskRepository
from app.schemas.risk import RiskStatusSchema
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/status", response_model=RiskStatusSchema)
async def risk_status(session: SessionDep, settings: SettingsDep) -> RiskStatusSchema:
    positions = await PositionRepository(session).get_open_positions()
    portfolio = PortfolioService(session, settings)
    snap = await portfolio.snapshot()
    daily = portfolio.daily_pnl_pct
    dd = float(snap.get("drawdown_pct") or 0)
    circuit = dd >= settings.circuit_breaker_drawdown
    return RiskStatusSchema(
        kill_switch=settings.kill_switch,
        circuit_breaker_triggered=circuit,
        open_positions=len(positions),
        daily_pnl_pct=round(daily, 4),
        drawdown_pct=round(dd, 4),
    )


@router.get("/events")
async def risk_events(session: SessionDep, limit: int = Query(100)) -> list:
    events = await RiskRepository(session).get_recent_events(limit)
    return [
        {
            "id": e.id,
            "level": e.level,
            "event_type": e.event_type,
            "message": e.message,
            "symbol": e.symbol,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
