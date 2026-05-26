"""Admin endpoints."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, SettingsDep
from app.core.constants import TradingMode
from app.core.security import verify_admin_token
from app.db.repositories.audit_repo import AuditRepository

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(verify_admin_token)])


@router.get("/audit")
async def audit_logs(session: SessionDep, limit: int = Query(200)) -> list:
    events = await AuditRepository(session).get_recent(limit)
    return [
        {
            "id": e.id,
            "correlation_id": e.correlation_id,
            "event_type": e.event_type,
            "payload_json": e.payload_json,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.post("/mode")
async def switch_mode(mode: TradingMode, settings: SettingsDep) -> dict:
    settings.trading_mode = mode
    return {
        "trading_mode": settings.trading_mode.value,
        "live_enabled": settings.live_trading_enabled,
        "is_live": settings.is_live_trading,
    }
