"""Coin scanner API."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SettingsDep
from app.services.coin_scanner_service import CoinScannerService
from app.services.trading_universe_service import TradingUniverseService

router = APIRouter(prefix="/scanner", tags=["scanner"])


@router.get("/status")
async def scanner_status(settings: SettingsDep) -> dict:
    snap = TradingUniverseService.last_scan_snapshot()
    return {
        "enabled": settings.scanner_enabled,
        "universe_size": settings.scanner_universe_size,
        "batch_size": settings.scanner_batch_size,
        "top_n": settings.scanner_top_n,
        "min_score": settings.scanner_min_score,
        "min_turnover_usdt": settings.scanner_min_turnover_usdt,
        "last_scan": {
            "top_symbols": snap.top_symbols if snap else [],
            "candidates_checked": snap.candidates_checked if snap else 0,
            "ranked": [
                {
                    "symbol": r.symbol,
                    "score": r.score,
                    "action": r.action,
                    "turnover_24h": r.turnover_24h,
                }
                for r in (snap.ranked[:20] if snap else [])
            ],
        }
        if snap
        else None,
    }


@router.post("/run")
async def scanner_run(session: SessionDep, settings: SettingsDep) -> dict:
    scanner = CoinScannerService(session, settings)
    snap = await scanner.scan()
    return {
        "top_symbols": snap.top_symbols,
        "candidates_checked": snap.candidates_checked,
        "ranked": [
            {
                "symbol": r.symbol,
                "score": r.score,
                "action": r.action,
                "reason": r.reason,
                "turnover_24h": r.turnover_24h,
            }
            for r in snap.ranked
        ],
    }


@router.get("/universe")
async def trading_universe(session: SessionDep, settings: SettingsDep) -> dict:
    universe = TradingUniverseService(session, settings)
    symbols, scan = await universe.resolve()
    return {
        "symbols": symbols,
        "scanner_top": scan.top_symbols if scan else [],
    }
