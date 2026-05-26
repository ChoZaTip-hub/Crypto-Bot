"""Risk endpoints."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep
from app.db.repositories.risk_repo import RiskRepository
from app.schemas.risk import RiskStatusSchema

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/status", response_model=RiskStatusSchema)
async def risk_status(session: SessionDep, settings: SettingsDep) -> RiskStatusSchema:
    from app.db.repositories.position_repo import PositionRepository

    positions = await PositionRepository(session).get_open_positions()
    return RiskStatusSchema(
        kill_switch=settings.kill_switch,
        circuit_breaker_triggered=False,
        open_positions=len(positions),
        daily_pnl_pct=0.0,
        drawdown_pct=0.0,
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
