"""Cross-asset ratio monitoring and user-approved swaps."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import SessionDep, SettingsDep
from app.services.audit_service import AuditService
from app.services.ratio_monitor_service import RatioMonitorService
from app.services.ratio_swap_service import RatioSwapService

router = APIRouter(prefix="/ratio-swaps", tags=["ratio-swaps"])


@router.get("/pairs")
async def list_pair_ratios(session: SessionDep, settings: SettingsDep) -> dict:
    monitor = RatioMonitorService(session, settings)
    return {"pairs": await monitor.get_all_pairs_dashboard()}


@router.get("/holdings")
async def get_holdings(session: SessionDep, settings: SettingsDep) -> dict:
    svc = RatioSwapService(session, settings, AuditService(session))
    return {"holdings": await svc.get_holdings(), "mode": settings.trading_mode.value}


@router.get("/proposals")
async def list_proposals(
    session: SessionDep,
    settings: SettingsDep,
    status: str = Query("pending"),
) -> dict:
    svc = RatioSwapService(session, settings, AuditService(session))
    if status == "pending":
        items = await svc.list_pending()
    else:
        items = await svc.list_recent(30)
    return {"proposals": items}


@router.post("/scan")
async def scan_proposals(session: SessionDep, settings: SettingsDep) -> dict:
    """Record ratios and create proposals for extreme pairs."""
    svc = RatioSwapService(session, settings, AuditService(session))
    created = await svc.scan_and_propose()
    await session.commit()
    return {"created": len(created), "proposals": created}


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: int, session: SessionDep, settings: SettingsDep) -> dict:
    svc = RatioSwapService(session, settings, AuditService(session))
    result = await svc.approve(proposal_id)
    await session.commit()
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "approve_failed"))
    return result


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: int,
    session: SessionDep,
    settings: SettingsDep,
    note: str | None = None,
) -> dict:
    svc = RatioSwapService(session, settings, AuditService(session))
    result = await svc.reject(proposal_id, note=note)
    await session.commit()
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "reject_failed"))
    return result
