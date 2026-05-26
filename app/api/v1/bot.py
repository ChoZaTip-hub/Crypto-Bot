"""Bot control endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import BackgroundManagerDep, BotManagerDep, SettingsDep
from app.core.security import verify_admin_token
from app.core.timeframes import label_for_timeframe
from app.schemas.config import BotConfigSchema, BotConfigUpdateSchema

router = APIRouter(prefix="/bot", tags=["bot"])


@router.get("/status")
async def bot_status(
    manager: BotManagerDep,
    background: BackgroundManagerDep,
    settings: SettingsDep,
) -> dict:
    return {
        "running": manager.is_running,
        "last_run_at": manager.last_run_at,
        "last_error": manager.last_error,
        "trading_mode": settings.trading_mode.value,
        "live_trading_enabled": settings.live_trading_enabled,
        "market_data_source": "bybit" if settings.use_bybit_market_data else "mock",
        "symbols": settings.symbol_whitelist,
        "timeframes": settings.timeframes,
        "timeframe_labels": {tf: label_for_timeframe(tf) for tf in settings.timeframes},
        "background": background.status,
        "memory_enabled": settings.memory_enabled,
        "learning_enabled": settings.learning_enabled,
    }


@router.post("/start")
async def start_bot(manager: BotManagerDep) -> dict:
    await manager.start()
    return {"status": "started", "running": manager.is_running}


@router.post("/stop")
async def stop_bot(manager: BotManagerDep) -> dict:
    await manager.stop()
    return {"status": "stopped", "running": manager.is_running}


@router.post("/run-once")
async def run_once(manager: BotManagerDep) -> dict:
    result = await manager.run_once()
    return {"status": "ok", "result": result}


@router.get("/config", response_model=BotConfigSchema)
async def get_config(settings: SettingsDep) -> BotConfigSchema:
    return BotConfigSchema(
        trading_mode=settings.trading_mode,
        live_trading_enabled=settings.live_trading_enabled,
        symbol_whitelist=settings.symbol_whitelist,
        timeframes=settings.timeframes,
        max_risk_per_trade=settings.max_risk_per_trade,
        max_daily_loss=settings.max_daily_loss,
        max_open_positions=settings.max_open_positions,
        kill_switch=settings.kill_switch,
    )


@router.patch("/config", dependencies=[Depends(verify_admin_token)])
async def update_config(
    update: BotConfigUpdateSchema,
    settings: SettingsDep,
) -> dict:
    if update.kill_switch is not None:
        settings.kill_switch = update.kill_switch
    return {"updated": update.model_dump(exclude_none=True)}
