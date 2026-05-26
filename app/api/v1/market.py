"""Market data endpoints."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep
from app.db.repositories.candle_repo import CandleRepository
from app.schemas.candle import CandleRead, MarketSnapshotSchema
from app.services.indicator_service import IndicatorService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/candles", response_model=list[CandleRead])
async def get_candles(
    session: SessionDep,
    symbol: str = Query(...),
    timeframe: str = Query("5"),
    limit: int = Query(100, le=500),
) -> list:
    repo = CandleRepository(session)
    return await repo.get_by_symbol_and_timeframe(symbol.upper(), timeframe, limit)


@router.get("/snapshot", response_model=MarketSnapshotSchema)
async def market_snapshot(
    session: SessionDep,
    symbol: str = Query(...),
    timeframe: str = Query("5"),
) -> MarketSnapshotSchema:
    repo = CandleRepository(session)
    latest = await repo.get_latest(symbol.upper(), timeframe)
    audit = AuditService(session)
    indicators = await IndicatorService(session, audit).compute_for_symbol(
        symbol.upper(), timeframe
    )
    return MarketSnapshotSchema(
        symbol=symbol.upper(),
        timeframe=timeframe,
        last_price=float(latest.close) if latest else 0.0,
        last_candle_ts=latest.open_time if latest else 0,
        indicators={k: float(v) for k, v in indicators.items() if isinstance(v, (int, float))},
    )
