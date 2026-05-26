"""AI trade analysis API."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import SessionDep, SettingsDep
from app.db.repositories.candle_repo import CandleRepository
from app.services.ai.trade_analyst import AiTradeAnalyst
from app.services.audit_service import AuditService
from app.services.indicator_service import IndicatorService
from app.services.live_price_service import fetch_display_price
from app.services.trade_plan_service import build_fresh_trade_plan

router = APIRouter(prefix="/ai", tags=["ai"])


async def _load_indicators(session, symbol: str, chart_tf: str) -> dict[str, dict]:
    candle_repo = CandleRepository(session)
    ind_svc = IndicatorService(session, AuditService(session))
    out: dict[str, dict] = {}
    for tf in list(dict.fromkeys([chart_tf, "5", "15", "30", "60", "240"])):
        rows = await candle_repo.get_by_symbol_and_timeframe(symbol, tf, 120)
        if len(rows) < 5:
            continue
        tf_ind = ind_svc.compute_from_ohlcv(
            [c.close for c in rows],
            [c.high for c in rows],
            [c.low for c in rows],
            [c.volume for c in rows],
        )
        out[tf] = {k: float(v) for k, v in tf_ind.items() if isinstance(v, (int, float))}
    return out


@router.get("/status")
async def ai_status(settings: SettingsDep) -> dict:
    analyst = AiTradeAnalyst(settings)
    mode = "chart_image" if settings.ai_use_chart_image else "structured_data"
    return {
        "enabled": settings.ai_enabled,
        "configured": analyst.available,
        "provider": settings.ai_provider,
        "model": settings.ai_model,
        "vision_model": settings.ai_vision_model,
        "auto_analyze": settings.ai_auto_analyze,
        "influence_trades": settings.ai_influence_trades,
        "use_chart_image": settings.ai_use_chart_image,
        "min_confidence_influence": settings.ai_min_confidence_influence,
        "mode": mode,
        "env_file": ".env в корне проекта",
        "note": (
            "ИИ получает свечи и индикаторы Bybit (как бот). "
            "При AI_USE_CHART_IMAGE=true — ещё PNG графика (нужен matplotlib)."
        ),
    }


@router.post("/analyze")
async def ai_analyze(
    session: SessionDep,
    settings: SettingsDep,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("5"),
) -> dict:
    symbol = symbol.upper()
    analyst = AiTradeAnalyst(settings)
    if not analyst.available:
        raise HTTPException(
            status_code=400,
            detail="AI_ENABLED=true и AI_API_KEY в .env (OpenAI или совместимый API)",
        )

    indicators_by_tf = await _load_indicators(session, symbol, timeframe)
    price_info = await fetch_display_price(symbol, settings)
    live_price = float(price_info.get("price") or 0)
    if live_price <= 0:
        raise HTTPException(status_code=400, detail="Нет цены Bybit для символа")

    plan = await build_fresh_trade_plan(
        session,
        settings,
        symbol,
        indicators_by_tf,
        chart_timeframe=timeframe,
        run_ai=True,
    )
    ai = (plan or {}).get("ai")
    if not ai:
        raise HTTPException(status_code=502, detail="ИИ не вернул ответ")
    return {"ai": ai, "plan": plan}
