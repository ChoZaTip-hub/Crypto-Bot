"""Track cross-asset ratios (BTC/ETH etc.) and detect extremes."""

from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.candle_repo import CandleRepository
from app.db.repositories.pair_ratio_repo import PairRatioRepository
from app.exchanges.bybit_client import BybitClient
from app.exchanges.mock_exchange import MockExchange
from app.utils.symbols import all_ratio_pairs, base_asset, usdt_symbol

logger = get_logger(__name__)


class RatioMonitorService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = PairRatioRepository(session)
        self._candle_repo = CandleRepository(session)
        self._bybit = BybitClient(settings)
        self._paper = MockExchange()

    async def _fetch_prices(self) -> dict[str, float]:
        prices: dict[str, float] = {}
        exchange = self._bybit if self._settings.use_bybit_market_data else self._paper
        if not self._settings.use_bybit_market_data:
            await self._paper.connect()
        for sym in self._settings.symbol_whitelist:
            asset = base_asset(sym)
            try:
                if self._settings.use_bybit_market_data:
                    prices[asset] = await self._bybit.fetch_last_price(sym)
                else:
                    prices[asset] = self._paper._base_price(sym)
            except Exception as exc:
                logger.warning("ratio_price_fetch_failed", symbol=sym, error=str(exc))
        return prices

    async def backfill_from_daily_candles(self, limit: int = 400) -> int:
        """Seed ratio history from stored D candles (BTC/ETH style pairs)."""
        count = 0
        for base, quote in all_ratio_pairs(self._settings.symbol_whitelist):
            existing = await self._repo.get_history(base, quote, limit=5)
            if len(existing) >= 5:
                continue
            bc = await self._candle_repo.get_by_symbol_and_timeframe(usdt_symbol(base), "D", limit)
            qc = await self._candle_repo.get_by_symbol_and_timeframe(usdt_symbol(quote), "D", limit)
            if len(bc) < 5 or len(qc) < 5:
                continue
            q_by_time = {c.open_time: c.close for c in qc}
            for cb in bc:
                if cb.open_time not in q_by_time:
                    continue
                pq = float(q_by_time[cb.open_time])
                if pq <= 0:
                    continue
                pb = float(cb.close)
                ts = cb.open_time
                if ts > 1_000_000_000_000:
                    ts = ts // 1000
                sampled = datetime.fromtimestamp(ts, tz=timezone.utc)
                await self._repo.save_snapshot(
                    {
                        "base_asset": base,
                        "quote_asset": quote,
                        "ratio": pb / pq,
                        "base_price_usdt": pb,
                        "quote_price_usdt": pq,
                        "sampled_at": sampled,
                        "source": "candle_d",
                    }
                )
                count += 1
        return count

    async def record_snapshots(self) -> dict[str, int]:
        """Store current ratio for every pair in symbol whitelist."""
        prices = await self._fetch_prices()
        now = datetime.now(timezone.utc)
        count = 0
        for base, quote in all_ratio_pairs(self._settings.symbol_whitelist):
            pb, pq = prices.get(base), prices.get(quote)
            if not pb or not pq or pq <= 0:
                continue
            ratio = pb / pq
            await self._repo.save_snapshot(
                {
                    "base_asset": base,
                    "quote_asset": quote,
                    "ratio": ratio,
                    "base_price_usdt": pb,
                    "quote_price_usdt": pq,
                    "sampled_at": now,
                    "source": "bybit" if self._settings.use_bybit_market_data else "mock",
                }
            )
            count += 1
        return {"pairs_recorded": count, "assets_priced": len(prices)}

    def _percentile(self, value: float, samples: list[float]) -> float:
        if not samples:
            return 50.0
        below = sum(1 for s in samples if s <= value)
        return 100.0 * below / len(samples)

    async def get_pair_analysis(self, base: str, quote: str) -> dict[str, Any] | None:
        history = await self._repo.get_history(base, quote, limit=500)
        if not history:
            prices = await self._fetch_prices()
            pb, pq = prices.get(base), prices.get(quote)
            if not pb or not pq:
                return None
            current = pb / pq
            return {
                "base_asset": base,
                "quote_asset": quote,
                "pair_label": f"{base}/{quote}",
                "ratio_current": current,
                "ratio_mean": current,
                "ratio_min": current,
                "ratio_max": current,
                "ratio_percentile": 50.0,
                "samples": 0,
                "base_price_usdt": pb,
                "quote_price_usdt": pq,
            }

        ratios = [h.ratio for h in history]
        current = ratios[0]
        mean = statistics.mean(ratios)
        mn, mx = min(ratios), max(ratios)
        pct = self._percentile(current, ratios)
        latest = history[0]

        # Reference windows (approximate by sample count if ~hourly)
        def _ref_slice(days: int) -> list[float]:
            n = min(len(ratios), max(1, days * 24))
            return ratios[:n]

        ref_30 = statistics.mean(_ref_slice(30)) if len(ratios) >= 5 else mean
        ref_365 = statistics.mean(_ref_slice(365)) if len(ratios) >= 24 else mean

        return {
            "base_asset": base,
            "quote_asset": quote,
            "pair_label": f"{base}/{quote}",
            "ratio_current": current,
            "ratio_mean": mean,
            "ratio_min": mn,
            "ratio_max": mx,
            "ratio_percentile": pct,
            "ratio_ref_30d": ref_30,
            "ratio_ref_365d": ref_365,
            "samples": len(ratios),
            "base_price_usdt": latest.base_price_usdt,
            "quote_price_usdt": latest.quote_price_usdt,
            "sampled_at": latest.sampled_at.isoformat() if latest.sampled_at else None,
        }

    async def get_all_pairs_dashboard(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for base, quote in all_ratio_pairs(self._settings.symbol_whitelist):
            row = await self.get_pair_analysis(base, quote)
            if row:
                out.append(row)
        return sorted(out, key=lambda r: r["pair_label"])
