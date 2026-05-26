"""Learning outcomes and adaptive weights API."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.services.audit_service import AuditService
from app.services.learning_service import LearningService

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/summary")
async def learning_summary(session: SessionDep) -> dict:
    svc = LearningService(session, AuditService(session))
    return await svc.get_summary()


@router.get("/outcomes")
async def learning_outcomes(
    session: SessionDep,
    symbol: str | None = Query(None),
    limit: int = Query(50, le=200),
) -> dict:
    from app.db.repositories.learning_outcome_repo import LearningOutcomeRepository

    repo = LearningOutcomeRepository(session)
    rows = await repo.get_recent(symbol=symbol.upper() if symbol else None, limit=limit)
    return {
        "outcomes": [
            {
                "symbol": o.symbol,
                "regime": o.regime,
                "sub_strategy": o.sub_strategy,
                "action": o.action,
                "pnl_pct": o.pnl_pct,
                "outcome": o.outcome,
                "exit_reason": o.exit_reason,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in rows
        ]
    }
