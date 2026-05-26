"""Chart memory: snapshots + change detection."""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AuditEventType
from app.core.logging import get_logger
from app.db.repositories.candle_repo import CandleRepository
from app.db.repositories.market_change_repo import MarketChangeRepository
from app.db.repositories.market_snapshot_repo import MarketSnapshotRepository
from app.db.repositories.strategy_decision_repo import StrategyDecisionRepository
from app.services.audit_service import AuditService
from app.services.indicator_service import IndicatorService

logger = get_logger(__name__)

CHANGE_THRESHOLDS = {
    "rsi_overbought": 70.0,
    "rsi_oversold": 30.0,
    "adx_trend": 25.0,
    "price_move_pct": 0.5,
}


class MemoryService:
    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self._snapshot_repo = MarketSnapshotRepository(session)
        self._change_repo = MarketChangeRepository(session)
        self._candle_repo = CandleRepository(session)
        self._decision_repo = StrategyDecisionRepository(session)
        self._indicator = IndicatorService(session, audit)
        self._audit = audit

    async def capture_symbol(
        self, symbol: str, timeframes: list[str], regime: str = "unknown"
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for tf in timeframes:
            candles = await self._candle_repo.get_by_symbol_and_timeframe(symbol, tf, limit=120)
            if len(candles) < 5:
                continue
            indicators = self._indicator.compute_from_ohlcv(
                [c.close for c in candles],
                [c.high for c in candles],
                [c.low for c in candles],
                [c.volume for c in candles],
            )
            if not indicators:
                continue
            last = candles[-1]
            await self._snapshot_repo.upsert_snapshot(
                symbol=symbol,
                timeframe=tf,
                open_time=last.open_time,
                close=float(last.close),
                regime=regime,
                indicators={k: float(v) for k, v in indicators.items() if isinstance(v, (int, float))},
            )
            changes = await self._detect_changes(symbol, tf, last.open_time, indicators)
            counts[tf] = 1 + len(changes)
        return counts

    async def _detect_changes(
        self, symbol: str, timeframe: str, open_time: int, indicators: dict[str, Any]
    ) -> list[dict]:
        prev = await self._snapshot_repo.get_latest(symbol, timeframe, before_open_time=open_time)
        if prev is None:
            return []
        try:
            old_ind = json.loads(prev.indicators_json)
        except json.JSONDecodeError:
            old_ind = {}
        detected: list[dict] = []

        def _add(change_type: str, severity: str, message: str, old_v: float | None, new_v: float | None) -> None:
            detected.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "change_type": change_type,
                    "severity": severity,
                    "message": message,
                    "old_value": old_v,
                    "new_value": new_v,
                    "open_time": open_time,
                }
            )

        close = float(indicators.get("close", 0))
        prev_close = float(old_ind.get("close", prev.close))
        if prev_close > 0:
            move_pct = abs(close - prev_close) / prev_close * 100
            if move_pct >= CHANGE_THRESHOLDS["price_move_pct"]:
                _add(
                    "price_move",
                    "warning" if move_pct > 1.0 else "info",
                    f"Цена {symbol} {timeframe}: {move_pct:.2f}%",
                    prev_close,
                    close,
                )

        for key, lo, hi, ctype in (
            ("rsi", CHANGE_THRESHOLDS["rsi_oversold"], CHANGE_THRESHOLDS["rsi_overbought"], "rsi_zone"),
            ("adx", 0, CHANGE_THRESHOLDS["adx_trend"], "adx_trend"),
        ):
            old_v = float(old_ind.get(key, 0))
            new_v = float(indicators.get(key, 0))
            if key == "rsi":
                if old_v < hi <= new_v or old_v > lo >= new_v:
                    _add(ctype, "info", f"RSI пересёк зону ({new_v:.1f})", old_v, new_v)
            elif key == "adx" and old_v < hi <= new_v:
                _add(ctype, "info", f"ADX вошёл в тренд ({new_v:.1f})", old_v, new_v)

        for ch in detected:
            await self._change_repo.save_change(ch)
            await self._audit.log(
                AuditEventType.MARKET_CHANGE,
                correlation_id=f"{symbol}:{timeframe}",
                payload=ch,
            )
        return detected

    async def get_context(self, symbol: str, timeframe: str = "5") -> dict[str, Any]:
        """Recent snapshots + changes + decisions for strategy context."""
        snapshots = await self._snapshot_repo.get_recent(symbol, timeframe, limit=20)
        changes = await self._change_repo.get_recent(symbol=symbol, limit=15)
        decisions = await self._decision_repo.get_recent(limit=30)
        symbol_decisions = [d for d in decisions if d.symbol == symbol][:10]
        return {
            "snapshots": [
                {
                    "open_time": s.open_time,
                    "close": s.close,
                    "regime": s.regime,
                    "indicators": json.loads(s.indicators_json),
                }
                for s in snapshots
            ],
            "recent_changes": [
                {
                    "change_type": c.change_type,
                    "message": c.message,
                    "severity": c.severity,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in changes
            ],
            "recent_actions": [
                {
                    "action": d.action,
                    "confidence": d.confidence,
                    "regime": d.regime,
                    "explanation": (d.explanation or "")[:120],
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in symbol_decisions
            ],
        }
