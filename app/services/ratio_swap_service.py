"""Propose and execute user-confirmed cross-asset ratio swaps."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditEventType
from app.core.logging import get_logger
from app.db.repositories.asset_holding_repo import AssetHoldingRepository
from app.db.repositories.ratio_swap_repo import RatioSwapRepository
from app.services.audit_service import AuditService
from app.services.ratio_monitor_service import RatioMonitorService
from app.utils.symbols import all_ratio_pairs

logger = get_logger(__name__)


class RatioSwapService:
    def __init__(self, session: AsyncSession, settings: Settings, audit: AuditService) -> None:
        self._session = session
        self._settings = settings
        self._audit = audit
        self._proposal_repo = RatioSwapRepository(session)
        self._holding_repo = AssetHoldingRepository(session)
        self._monitor = RatioMonitorService(session, settings)

    async def ensure_paper_holdings(self) -> dict[str, float]:
        """Seed equal-USDT paper holdings on first run."""
        existing = await self._holding_repo.get_all("paper")
        if existing:
            return {h.asset: h.qty for h in existing}

        prices = await self._monitor._fetch_prices()
        bases = sorted(prices.keys())
        if not bases:
            return {}

        per_asset_usdt = self._settings.paper_initial_balance / max(len(bases), 1)
        holdings: dict[str, float] = {}
        for asset in bases:
            p = prices[asset]
            qty = per_asset_usdt / p if p > 0 else 0.0
            await self._holding_repo.set_qty(asset, qty, "paper")
            holdings[asset] = qty
        return holdings

    async def get_holdings(self) -> dict[str, float]:
        await self.ensure_paper_holdings()
        rows = await self._holding_repo.get_all("paper")
        return {h.asset: h.qty for h in rows}

    def _build_explanation(
        self,
        *,
        direction: str,
        base: str,
        quote: str,
        from_asset: str,
        to_asset: str,
        from_qty: float,
        to_qty: float,
        analysis: dict[str, Any],
    ) -> str:
        cur = analysis["ratio_current"]
        mn = analysis.get("ratio_min", cur)
        mx = analysis.get("ratio_max", cur)
        mean = analysis.get("ratio_mean", cur)
        pct = analysis.get("ratio_percentile", 50)
        ref30 = analysis.get("ratio_ref_30d")
        ref365 = analysis.get("ratio_ref_365d")

        lines = [
            f"═══ Предложение обмена {from_asset} → {to_asset} ═══",
            "",
            f"Пара {base}/{quote}: сейчас 1 {base} = {cur:.4f} {quote}",
            f"История бота: мин {mn:.4f} · среднее {mean:.4f} · макс {mx:.4f}",
            f"Позиция в истории: {pct:.0f}% (100% = максимум за период наблюдений)",
        ]
        if ref30 is not None:
            lines.append(f"Среднее ~30д: {ref30:.4f}")
        if ref365 is not None:
            lines.append(f"Среднее ~365д: {ref365:.4f}")
        lines.extend(
            [
                "",
                "💡 Логика накопления:",
                f"  • При высоком соотношении ({base} дороже {quote}) — меняем {base} на {quote}.",
                f"  • При низком соотношении — возвращаемся из {quote} в {base}.",
                "  • Пример: 1 BTC при курсе 36 ETH → 36 ETH; при курсе 12 → ~3 BTC.",
                "",
                f"🔄 Предлагаемый обмен: {from_qty:.8f} {from_asset} → {to_qty:.8f} {to_asset}",
                f"Направление: {direction}",
                "",
                "Подтверди обмен в панели или отклони — без подтверждения сделка не исполняется.",
            ]
        )
        return "\n".join(lines)

    async def scan_and_propose(self) -> list[dict[str, Any]]:
        """Create pending proposals when ratio is at historical extreme."""
        if not self._settings.ratio_swap_enabled:
            return []

        await self._monitor.backfill_from_daily_candles()
        await self._monitor.record_snapshots()
        holdings = await self.get_holdings()
        created: list[dict[str, Any]] = []
        expires = datetime.now(timezone.utc) + timedelta(hours=self._settings.ratio_proposal_ttl_hours)

        for base, quote in all_ratio_pairs(self._settings.symbol_whitelist):
            if await self._proposal_repo.has_pending_for_pair(base, quote):
                continue

            analysis = await self._monitor.get_pair_analysis(base, quote)
            if not analysis or analysis["samples"] < self._settings.ratio_min_snapshots:
                continue

            pct = analysis["ratio_percentile"]
            high = self._settings.ratio_high_percentile * 100
            low = self._settings.ratio_low_percentile * 100
            cur = analysis["ratio_current"]

            direction: str | None = None
            from_asset: str | None = None
            to_asset: str | None = None

            # Ratio high: base expensive vs quote -> rotate base to quote
            if pct >= high and holdings.get(base, 0) > 0:
                direction = "base_to_quote"
                from_asset, to_asset = base, quote
            # Ratio low: base cheap vs quote -> rotate quote to base
            elif pct <= low and holdings.get(quote, 0) > 0:
                direction = "quote_to_base"
                from_asset, to_asset = quote, base

            if not direction or not from_asset or not to_asset:
                continue

            from_qty = holdings[from_asset] * self._settings.ratio_swap_fraction
            if from_qty <= 0:
                continue

            if direction == "base_to_quote":
                to_qty = from_qty * cur
            else:
                to_qty = from_qty / cur if cur > 0 else 0

            if to_qty <= 0:
                continue

            corr = str(uuid.uuid4())
            explanation = self._build_explanation(
                direction=direction,
                base=base,
                quote=quote,
                from_asset=from_asset,
                to_asset=to_asset,
                from_qty=from_qty,
                to_qty=to_qty,
                analysis=analysis,
            )

            prop = await self._proposal_repo.create_proposal(
                {
                    "correlation_id": corr,
                    "base_asset": base,
                    "quote_asset": quote,
                    "direction": direction,
                    "from_asset": from_asset,
                    "to_asset": to_asset,
                    "from_qty": from_qty,
                    "to_qty": to_qty,
                    "ratio_current": cur,
                    "ratio_mean": analysis.get("ratio_mean"),
                    "ratio_min_hist": analysis.get("ratio_min"),
                    "ratio_max_hist": analysis.get("ratio_max"),
                    "ratio_percentile": pct,
                    "status": "pending",
                    "explanation": explanation,
                    "expires_at": expires,
                }
            )
            await self._audit.log(
                AuditEventType.RATIO_SWAP_PROPOSED,
                correlation_id=corr,
                payload={"proposal_id": prop.id, "pair": f"{base}/{quote}", "direction": direction},
            )
            created.append(self._proposal_dict(prop))

        return created

    async def approve(self, proposal_id: int) -> dict[str, Any]:
        prop = await self._proposal_repo.get_by_id(proposal_id)
        if not prop or prop.status != "pending":
            return {"ok": False, "error": "proposal_not_found_or_not_pending"}

        holdings = await self.get_holdings()
        available = holdings.get(prop.from_asset, 0)
        if available < prop.from_qty * 0.999:
            prop.status = "rejected"
            prop.user_note = f"Недостаточно {prop.from_asset}: есть {available}"
            prop.resolved_at = datetime.now(timezone.utc)
            await self._session.flush()
            return {"ok": False, "error": "insufficient_balance", "available": available}

        # Execute paper swap
        new_from = available - prop.from_qty
        new_to = holdings.get(prop.to_asset, 0) + prop.to_qty
        await self._holding_repo.set_qty(prop.from_asset, new_from, "paper")
        await self._holding_repo.set_qty(prop.to_asset, new_to, "paper")

        prop.status = "executed"
        prop.resolved_at = datetime.now(timezone.utc)
        await self._session.flush()

        await self._audit.log(
            AuditEventType.RATIO_SWAP_EXECUTED,
            correlation_id=prop.correlation_id,
            payload={
                "proposal_id": prop.id,
                "from": f"{prop.from_qty} {prop.from_asset}",
                "to": f"{prop.to_qty} {prop.to_asset}",
                "holdings_after": await self.get_holdings(),
            },
        )
        return {"ok": True, "proposal": self._proposal_dict(prop), "holdings": await self.get_holdings()}

    async def reject(self, proposal_id: int, note: str | None = None) -> dict[str, Any]:
        prop = await self._proposal_repo.get_by_id(proposal_id)
        if not prop or prop.status != "pending":
            return {"ok": False, "error": "proposal_not_found_or_not_pending"}
        prop.status = "rejected"
        prop.user_note = note
        prop.resolved_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._audit.log(
            AuditEventType.RATIO_SWAP_REJECTED,
            correlation_id=prop.correlation_id,
            payload={"proposal_id": prop.id, "note": note},
        )
        return {"ok": True, "proposal": self._proposal_dict(prop)}

    async def list_pending(self) -> list[dict[str, Any]]:
        return [self._proposal_dict(p) for p in await self._proposal_repo.get_pending()]

    async def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        return [self._proposal_dict(p) for p in await self._proposal_repo.get_recent(limit)]

    def _proposal_dict(self, p) -> dict[str, Any]:
        return {
            "id": p.id,
            "correlation_id": p.correlation_id,
            "base_asset": p.base_asset,
            "quote_asset": p.quote_asset,
            "pair_label": f"{p.base_asset}/{p.quote_asset}",
            "direction": p.direction,
            "from_asset": p.from_asset,
            "to_asset": p.to_asset,
            "from_qty": p.from_qty,
            "to_qty": p.to_qty,
            "ratio_current": p.ratio_current,
            "ratio_mean": p.ratio_mean,
            "ratio_min_hist": p.ratio_min_hist,
            "ratio_max_hist": p.ratio_max_hist,
            "ratio_percentile": p.ratio_percentile,
            "status": p.status,
            "explanation": p.explanation,
            "user_note": p.user_note,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "expires_at": p.expires_at.isoformat() if p.expires_at else None,
            "resolved_at": p.resolved_at.isoformat() if p.resolved_at else None,
        }
