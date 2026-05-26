"""Health endpoints."""

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.db.init_db import DatabaseInitializer

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health(request: Request) -> dict:
    settings = get_settings()
    db_ok = False
    if hasattr(request.app.state, "db_manager"):
        init = DatabaseInitializer(request.app.state.db_manager.engine)
        db_ok = await init.ping()
    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "trading_mode": settings.trading_mode.value,
        "live_enabled": settings.live_trading_enabled,
        "database": "up" if db_ok else "down",
    }


@router.get("/ready")
async def ready() -> dict:
    return {"ready": True}
