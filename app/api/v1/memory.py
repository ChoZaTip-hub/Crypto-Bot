"""Market memory API — snapshots and changes."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep
from app.db.repositories.market_change_repo import MarketChangeRepository
from app.db.repositories.market_snapshot_repo import MarketSnapshotRepository
from app.services.audit_service import AuditService
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/snapshots")
async def list_snapshots(
    session: SessionDep,
    settings: SettingsDep,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("5"),
    limit: int = Query(30, le=200),
) -> dict:
    symbol = symbol.upper()
    repo = MarketSnapshotRepository(session)
    rows = await repo.get_recent(symbol, timeframe, limit=limit)
    import json

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "snapshots": [
            {
                "open_time": r.open_time,
                "close": r.close,
                "regime": r.regime,
                "indicators": json.loads(r.indicators_json),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/changes")
async def list_changes(
    session: SessionDep,
    symbol: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> dict:
    repo = MarketChangeRepository(session)
    rows = await repo.get_recent(symbol=symbol.upper() if symbol else None, limit=limit)
    return {
        "changes": [
            {
                "symbol": c.symbol,
                "timeframe": c.timeframe,
                "change_type": c.change_type,
                "severity": c.severity,
                "message": c.message,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ]
    }


@router.get("/context")
async def memory_context(
    session: SessionDep,
    settings: SettingsDep,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("5"),
) -> dict:
    memory = MemoryService(session, AuditService(session))
    return await memory.get_context(symbol.upper(), timeframe)
