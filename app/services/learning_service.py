"""Adaptive learning: rule-based weights + lightweight statistical bias."""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditEventType
from app.core.logging import get_logger
from app.db.repositories.learning_outcome_repo import LearningOutcomeRepository
from app.db.repositories.strategy_weight_repo import StrategyWeightRepository
from app.services.audit_service import AuditService

logger = get_logger(__name__)


class LearningService:
    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self._outcome_repo = LearningOutcomeRepository(session)
        self._weight_repo = StrategyWeightRepository(session)
        self._audit = audit

    async def record_outcome(
        self,
        *,
        correlation_id: str | None,
        symbol: str,
        regime: str,
        sub_strategy: str,
        action: str,
        entry_price: float,
        exit_price: float,
        exit_reason: str,
        bars_held: int = 0,
        features: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if entry_price <= 0:
            return {}
        is_long = action.upper() == "BUY"
        if is_long:
            pnl_pct = (exit_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - exit_price) / entry_price * 100

        if pnl_pct > 0.05:
            outcome = "win"
        elif pnl_pct < -0.05:
            outcome = "loss"
        else:
            outcome = "breakeven"

        row = await self._outcome_repo.save_outcome(
            {
                "correlation_id": correlation_id,
                "symbol": symbol,
                "regime": regime,
                "sub_strategy": sub_strategy,
                "action": action,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl_pct": pnl_pct,
                "outcome": outcome,
                "exit_reason": exit_reason,
                "bars_held": bars_held,
                "features_json": json.dumps(features or {}),
            }
        )
        weight_row = await self._weight_repo.update_from_outcome(
            regime, sub_strategy, pnl_pct, outcome
        )
        await self._audit.log(
            AuditEventType.LEARNING_OUTCOME,
            correlation_id=correlation_id or symbol,
            payload={
                "symbol": symbol,
                "outcome": outcome,
                "pnl_pct": pnl_pct,
                "exit_reason": exit_reason,
                "new_weight": weight_row.weight,
            },
        )
        return {
            "id": row.id,
            "outcome": outcome,
            "pnl_pct": pnl_pct,
            "weight": weight_row.weight,
            "ml_bias": weight_row.ml_bias,
        }

    async def get_adjustment(self, regime: str) -> dict[str, float]:
        """Weights for trend / mean_reversion / combined used by strategy."""
        weights = await self._weight_repo.get_all()
        result = {"trend": 1.0, "mean_reversion": 1.0, "combined": 1.0, "ml_confidence_bias": 0.0}
        for w in weights:
            if w.regime != regime and w.regime != "unknown":
                continue
            if w.sub_strategy in result:
                result[w.sub_strategy] = w.weight
            result["ml_confidence_bias"] += w.ml_bias * 0.1
        result["ml_confidence_bias"] = max(-0.2, min(0.2, result["ml_confidence_bias"]))
        return result

    async def get_summary(self) -> dict[str, Any]:
        outcomes = await self._outcome_repo.get_recent(limit=100)
        weights = await self._weight_repo.get_all()
        wins = sum(1 for o in outcomes if o.outcome == "win")
        losses = sum(1 for o in outcomes if o.outcome == "loss")
        return {
            "total_outcomes": len(outcomes),
            "wins": wins,
            "losses": losses,
            "win_rate": wins / (wins + losses) if (wins + losses) else 0.0,
            "weights": [
                {
                    "regime": w.regime,
                    "sub_strategy": w.sub_strategy,
                    "weight": w.weight,
                    "ml_bias": w.ml_bias,
                    "wins": w.wins,
                    "losses": w.losses,
                }
                for w in weights
            ],
            "recent": [
                {
                    "symbol": o.symbol,
                    "outcome": o.outcome,
                    "pnl_pct": o.pnl_pct,
                    "exit_reason": o.exit_reason,
                    "regime": o.regime,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in outcomes[:15]
            ],
        }
