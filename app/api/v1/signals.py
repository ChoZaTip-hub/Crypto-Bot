"""Signal endpoints."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.db.repositories.signal_repo import SignalRepository
from app.schemas.signal import SignalRead

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalRead])
async def list_signals(
    session: SessionDep,
    symbol: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> list:
    repo = SignalRepository(session)
    if symbol:
        latest = await repo.get_latest(symbol.upper())
        return [latest] if latest else []
    return await repo.get_all(limit=limit)
