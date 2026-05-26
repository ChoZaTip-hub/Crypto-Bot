"""Bot control endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import BackgroundManagerDep, BotManagerDep, SettingsDep
from app.core.security import verify_admin_token
from app.core.timeframes import label_for_timeframe
from app.schemas.config import (
    BotConfigSchema,
    BotConfigUpdateSchema,
    TradingParamsSchema,
    TradingParamsUpdateSchema,
)

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
        "bybit_category": settings.bybit_category,
        "trading_params": _trading_params_dict(settings),
        "last_cycle_summary": _last_cycle_summary(manager),
    }


def _trading_params_dict(settings) -> dict:
    return {
        "position_size_mode": settings.position_size_mode,
        "order_usdt": settings.order_usdt,
        "entry_order_type": settings.entry_order_type,
        "max_risk_per_trade": settings.max_risk_per_trade,
        "paper_initial_balance": settings.paper_initial_balance,
    }


def _last_cycle_summary(manager) -> list[dict]:
    last = manager.last_result or {}
    out = []
    for d in last.get("decisions") or []:
        out.append(
            {
                "symbol": d.get("symbol"),
                "action": d.get("action"),
                "activity": d.get("activity"),
                "risk_allowed": d.get("risk_allowed"),
                "risk_blocks": d.get("risk_blocks"),
                "order": d.get("order"),
                "suggested_usdt": d.get("suggested_usdt"),
            }
        )
    return out


@router.get("/trading-params", response_model=TradingParamsSchema)
async def get_trading_params(settings: SettingsDep) -> TradingParamsSchema:
    return TradingParamsSchema(
        position_size_mode=settings.position_size_mode,
        order_usdt=settings.order_usdt,
        entry_order_type=settings.entry_order_type,
        max_risk_per_trade=settings.max_risk_per_trade,
    )


@router.post("/trading-params")
async def update_trading_params(
    body: TradingParamsUpdateSchema,
    settings: SettingsDep,
) -> dict:
    if body.position_size_mode is not None:
        if body.position_size_mode not in ("fixed_usdt", "risk_percent"):
            raise HTTPException(status_code=400, detail="position_size_mode: fixed_usdt | risk_percent")
        settings.position_size_mode = body.position_size_mode
    if body.order_usdt is not None:
        settings.order_usdt = body.order_usdt
    if body.entry_order_type is not None:
        if body.entry_order_type not in ("Market", "Limit"):
            raise HTTPException(status_code=400, detail="entry_order_type: Market | Limit")
        settings.entry_order_type = body.entry_order_type
    if body.max_risk_per_trade is not None:
        settings.max_risk_per_trade = body.max_risk_per_trade
    return {"ok": True, "trading_params": _trading_params_dict(settings)}


@router.post("/start")
async def start_bot(manager: BotManagerDep) -> dict:
    await manager.start()
    return {
        "status": "started",
        "running": manager.is_running,
        "hint": "Первый цикл запускается сразу. Сделка — при BUY/SELL и прохождении риска.",
    }


@router.post("/stop")
async def stop_bot(manager: BotManagerDep) -> dict:
    await manager.stop()
    return {"status": "stopped", "running": manager.is_running}


@router.post("/run-once")
async def run_once(manager: BotManagerDep) -> dict:
    try:
        result = await manager.run_once()
        return {"status": "ok", "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
