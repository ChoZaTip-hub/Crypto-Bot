"""Rank Bybit USDT spot pairs for autonomous trading universe."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.candle_repo import CandleRepository
from app.exchanges.bybit_rest import BybitRestClient
from app.services.indicator_service import IndicatorService
from app.services.market_analysis_service import _bias_for_tf, _tf_weight
from app.services.setup_scanner import scan_timeframe_setups
from app.services.symbol_universe import fetch_bybit_spot_usdt_symbols
from app.strategies.multi_timeframe_strategy import MultiTimeframeStrategy

logger = get_logger(__name__)

_scan_offset = 0


@dataclass
class CoinScanResult:
    symbol: str
    score: float
    action: str
    reason: str
    turnover_24h: float = 0.0


@dataclass
class ScannerSnapshot:
    scanned_at: float
    candidates_checked: int
    ranked: list[CoinScanResult]
    top_symbols: list[str]


class CoinScannerService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._candles = CandleRepository(session)
        from app.services.audit_service import AuditService

        self._indicators = IndicatorService(session, AuditService(session))

    async def scan(self) -> ScannerSnapshot:
        global _scan_offset
        universe = await fetch_bybit_spot_usdt_symbols(
            self._settings, limit=self._settings.scanner_universe_size
        )
        tickers = await self._fetch_turnover_map()
        batch = self._settings.scanner_batch_size
        start = _scan_offset % max(1, len(universe))
        _scan_offset = (start + batch) % max(1, len(universe))
        slice_syms = []
        for i in range(batch):
            if not universe:
                break
            slice_syms.append(universe[(start + i) % len(universe)])

        ranked: list[CoinScanResult] = []
        mtf = MultiTimeframeStrategy()
        for symbol in slice_syms:
            try:
                result = await self._score_symbol(symbol, mtf, tickers.get(symbol, 0.0))
                if result:
                    ranked.append(result)
            except Exception as exc:
                logger.debug("scanner_symbol_skip", symbol=symbol, error=str(exc))

        ranked.sort(key=lambda r: -r.score)
        top = [r.symbol for r in ranked if r.score >= self._settings.scanner_min_score]
        top = top[: self._settings.scanner_top_n]

        return ScannerSnapshot(
            scanned_at=time.time(),
            candidates_checked=len(slice_syms),
            ranked=ranked[:20],
            top_symbols=top,
        )

    async def _fetch_turnover_map(self) -> dict[str, float]:
        try:
            client = BybitRestClient(self._settings)
            return await client.fetch_spot_turnover_24h()
        except Exception as exc:
            logger.warning("scanner_tickers_failed", error=str(exc))
            return {}

    async def _score_symbol(
        self, symbol: str, mtf: MultiTimeframeStrategy, turnover: float
    ) -> CoinScanResult | None:
        min_turnover = self._settings.scanner_min_turnover_usdt
        if turnover > 0 and turnover < min_turnover:
            return None

        tf_data: dict[str, dict] = {}
        live_price = 0.0
        for tf in self._settings.scanner_timeframes:
            rows = await self._candles.get_by_symbol_and_timeframe(symbol, tf, 120)
            if len(rows) < 30:
                client = BybitRestClient(self._settings)
                live_candles = await client.fetch_klines(symbol, tf, limit=120)
                if len(live_candles) < 30:
                    continue
                closes = [c.close for c in live_candles]
                highs = [c.high for c in live_candles]
                lows = [c.low for c in live_candles]
                vols = [c.volume for c in live_candles]
                live_price = float(live_candles[-1].close)
            else:
                closes = [c.close for c in rows]
                highs = [c.high for c in rows]
                lows = [c.low for c in rows]
                vols = [c.volume for c in rows]
                live_price = float(rows[-1].close)
            ind = self._indicators.compute_from_ohlcv(closes, highs, lows, vols)
            tf_data[tf] = {k: float(v) for k, v in ind.items() if isinstance(v, (int, float))}
            tf_data[tf]["close"] = live_price

        if not tf_data or live_price <= 0:
            return None

        from app.strategies.base import StrategyInputs

        inputs = StrategyInputs(symbol=symbol, timeframes=tf_data, live_price=live_price)
        inputs.regime = mtf._detect_regime(inputs)
        bundle = await mtf.decide_detailed(inputs)
        action = bundle.signal.action.value

        bull = bear = 0.0
        for tf, ind in tf_data.items():
            bias, _ = _bias_for_tf(ind)
            w = _tf_weight(tf)
            if bias == "bullish":
                bull += w
            elif bias == "bearish":
                bear += w
        edge = bull - bear

        setups = scan_timeframe_setups(symbol, tf_data, live_price)
        setup_bonus = 0.0
        if setups:
            setup_bonus = max(float(s.get("weight", 1)) for s in setups) * 0.5

        vol_bonus = 0.0
        if turnover > 0:
            vol_bonus = min(3.0, turnover / max(min_turnover, 1.0) * 0.3)

        conf = float(bundle.signal.confidence or 0)
        score = abs(edge) + conf * 2 + setup_bonus + vol_bonus
        if action == "HOLD":
            score *= 0.35

        from app.risk.atr import atr_pct_from_timeframes

        atr_pct = atr_pct_from_timeframes(tf_data)
        if atr_pct > self._settings.max_atr_pct:
            score *= 0.5

        return CoinScanResult(
            symbol=symbol,
            score=round(score, 3),
            action=action,
            reason=bundle.signal.reason or "",
            turnover_24h=turnover,
        )
