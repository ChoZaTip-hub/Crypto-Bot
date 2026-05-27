"""Display trade plan — always from current market price, not stale DB signals."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import SignalAction
from app.core.timeframes import label_for_timeframe
from app.db.repositories.position_repo import PositionRepository
from app.services.audit_service import AuditService
from app.services.live_price_service import fetch_display_price
from app.services.setup_scanner import enrich_plan_with_setups, scan_timeframe_setups
from app.strategies.base import StrategyInputs, StrategySignal
from app.strategies.levels import apply_live_trade_levels, pick_atr
from app.strategies.multi_timeframe_strategy import MultiTimeframeStrategy


def _plan_dict(
    *,
    action: str,
    entry: float | None,
    stop_loss: float | None,
    take_profit: float | None,
    live_price: float,
    source: str,
    confidence: float = 0.0,
    reason: str = "",
    regime: str | None = None,
    horizon_tf: str = "5",
    atr: float = 0.0,
) -> dict[str, Any]:
    return {
        "symbol": "",
        "action": action,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "confidence": confidence,
        "reason": reason,
        "regime": regime,
        "source": source,
        "live_price": live_price,
        "atr": atr,
        "horizon_tf": horizon_tf,
        "horizon_label": label_for_timeframe(horizon_tf),
        "horizon_note": (
            f"Уровни от текущей цены Bybit и ATR ({label_for_timeframe(horizon_tf)}). "
            "При каждом цикле и обновлении страницы вход = цена сейчас."
        ),
    }


async def _finalize_with_ai(
    plan: dict[str, Any],
    *,
    settings: Settings,
    symbol: str,
    live_price: float,
    indicators_by_tf: dict[str, dict],
    chart_timeframe: str,
    regime: str | None,
    run_ai: bool,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    if not run_ai or not settings.ai_enabled:
        return plan
    from app.services.ai.integration import attach_ai_to_plan

    candle_rows = None
    if session and settings.ai_use_chart_image:
        from app.db.repositories.candle_repo import CandleRepository

        chart_tf = chart_timeframe if chart_timeframe in indicators_by_tf else "5"
        candle_rows = await CandleRepository(session).get_by_symbol_and_timeframe(
            symbol, chart_tf, 80
        )
    setups = scan_timeframe_setups(symbol, indicators_by_tf, live_price)
    return await attach_ai_to_plan(
        plan,
        settings,
        symbol=symbol,
        live_price=live_price,
        chart_timeframe=chart_timeframe,
        regime=regime,
        indicators_by_tf=indicators_by_tf,
        setups=setups,
        candle_rows=candle_rows,
    )


async def build_fresh_trade_plan(
    session: AsyncSession,
    settings: Settings,
    symbol: str,
    indicators_by_tf: dict[str, dict],
    *,
    candle_fallback_close: float = 0.0,
    chart_timeframe: str = "5",
    run_ai: bool | None = None,
) -> dict[str, Any] | None:
    """Fresh MTF decision + live entry/SL/TP (not from old signals table)."""
    symbol = symbol.upper()
    open_pos = await PositionRepository(session).get_by_symbol(symbol)
    price_info = await fetch_display_price(symbol, settings)
    live_price = float(price_info.get("price") or 0)
    if live_price <= 0 and candle_fallback_close > 0:
        live_price = candle_fallback_close
    if live_price <= 0:
        return None

    do_ai = (
        run_ai
        if run_ai is not None
        else bool(settings.ai_enabled and settings.ai_auto_analyze)
    )
    last_regime: str | None = None

    def _resolve_display_tf() -> str:
        if chart_timeframe in indicators_by_tf:
            return chart_timeframe
        for fb in (chart_timeframe, "5", "15", "30", "60", "240", "1", "3", "D"):
            if fb in indicators_by_tf:
                return fb
        return chart_timeframe

    def _finalize(plan: dict[str, Any], regime: str | None = None) -> dict[str, Any]:
        nonlocal last_regime
        last_regime = regime
        plan["symbol"] = symbol
        plan["live_price"] = live_price
        plan["chart_timeframe"] = chart_timeframe
        plan["chart_timeframe_label"] = label_for_timeframe(chart_timeframe)
        setups = scan_timeframe_setups(symbol, indicators_by_tf, live_price)
        plan = enrich_plan_with_setups(plan, setups)
        chart_setup = next((s for s in setups if s["timeframe"] == chart_timeframe), None)
        if chart_setup:
            plan["chart_setup"] = chart_setup
        display_tf = _resolve_display_tf()
        if plan.get("action") in ("BUY", "SELL"):
            plan["entry"] = live_price
            sig = apply_live_trade_levels(
                StrategySignal(
                    symbol=symbol,
                    action=SignalAction.BUY if plan["action"] == "BUY" else SignalAction.SELL,
                    confidence=float(plan.get("confidence") or 0),
                    reason=plan.get("reason") or "",
                    stop_loss=plan.get("stop_loss"),
                    take_profit=plan.get("take_profit"),
                ),
                live_price,
                indicators_by_tf,
                horizon_tf=display_tf,
            )
            plan["stop_loss"] = sig.stop_loss
            plan["take_profit"] = sig.take_profit
            plan["horizon_tf"] = display_tf
            plan["horizon_label"] = label_for_timeframe(display_tf)
            plan["atr"] = pick_atr(indicators_by_tf, prefer_tf=display_tf)
        elif chart_setup:
            plan["horizon_tf"] = chart_timeframe
            plan["horizon_label"] = label_for_timeframe(chart_timeframe)
            plan["suggested_chart_action"] = chart_setup["action"]
            plan["entry"] = chart_setup["entry"]
            plan["stop_loss"] = chart_setup["stop_loss"]
            plan["take_profit"] = chart_setup["take_profit"]
        if plan.get("primary_setup"):
            ps = plan["primary_setup"]
            plan["setup_timeframe_label"] = ps.get("label")
            plan["setup_timeframe"] = ps.get("timeframe")
        tf_lbl = label_for_timeframe(display_tf if plan.get("action") in ("BUY", "SELL") else chart_timeframe)
        plan["analysis_note"] = (
            f"{symbol}: цена Bybit {live_price:,.2f} · график {tf_lbl}. "
            f"Вход/SL/TP — ATR выбранного ТФ. MTF: {plan.get('action')} — {plan.get('reason', '')[:80]}"
        )
        return plan

    async def _done(plan: dict[str, Any]) -> dict[str, Any]:
        return await _finalize_with_ai(
            plan,
            settings=settings,
            symbol=symbol,
            live_price=live_price,
            indicators_by_tf=indicators_by_tf,
            chart_timeframe=chart_timeframe,
            regime=last_regime,
            run_ai=do_ai,
            session=session,
        )

    if open_pos:
        return await _done(
            _finalize(
            _plan_dict(
            action=open_pos.side.upper() if open_pos.side else "BUY",
            entry=float(open_pos.entry_price),
            stop_loss=open_pos.stop_loss,
            take_profit=open_pos.take_profit,
            live_price=live_price,
            source="open_position",
            reason="Позиция уже открыта — вход зафиксирован при сделке",
            horizon_tf=chart_timeframe,
            atr=pick_atr(indicators_by_tf, prefer_tf=chart_timeframe),
            )
            )
        )

    if not indicators_by_tf:
        return await _done(
            _finalize(
            _plan_dict(
            action="HOLD",
            entry=None,
            stop_loss=None,
            take_profit=None,
            live_price=live_price,
            source="no_indicators",
            reason="Загрузите свечи (кнопка «Загрузить свечи»)",
            horizon_tf=chart_timeframe,
            )
            )
        )

    chart_tf = chart_timeframe if chart_timeframe in indicators_by_tf else "5"
    mtf = MultiTimeframeStrategy()
    inputs = StrategyInputs(
        symbol=symbol,
        timeframes=indicators_by_tf,
        live_price=live_price,
    )
    inputs.regime = mtf._detect_regime(inputs)
    bundle = await mtf.decide_detailed(inputs)
    signal = apply_live_trade_levels(
        bundle.signal, live_price, indicators_by_tf, horizon_tf=chart_tf
    )
    atr = pick_atr(indicators_by_tf, prefer_tf=chart_tf)
    analyzed_tfs = sorted(indicators_by_tf.keys(), key=lambda x: (len(x), x))

    if signal.action == SignalAction.HOLD:
        return await _done(
            _finalize(
                _plan_dict(
                    action="HOLD",
                    entry=None,
                    stop_loss=None,
                    take_profit=None,
                    live_price=live_price,
                    source="fresh_analysis",
                    confidence=signal.confidence,
                    reason=signal.reason or "Нет явного входа на выбранных ТФ",
                    regime=inputs.regime,
                    horizon_tf=chart_tf,
                    atr=atr,
                ),
                regime=inputs.regime,
            )
        )

    return await _done(
        _finalize(
            _plan_dict(
                action=signal.action.value,
                entry=live_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                live_price=live_price,
                source="live_market",
                confidence=signal.confidence,
                reason=signal.reason,
                regime=inputs.regime,
                horizon_tf=chart_tf,
                atr=atr,
            ),
            regime=inputs.regime,
        )
    )


async def build_quick_live_plan(
    session: AsyncSession,
    settings: Settings,
    symbol: str,
    chart_timeframe: str = "5",
) -> dict[str, Any] | None:
    """Lightweight plan for 2s price poll — 5m indicators + fresh decision."""
    from app.db.repositories.candle_repo import CandleRepository
    from app.services.indicator_service import IndicatorService

    symbol = symbol.upper()
    candle_repo = CandleRepository(session)
    ind_svc = IndicatorService(session, AuditService(session))
    indicators_by_tf: dict[str, dict] = {}
    fallback = 0.0
    tfs = list(dict.fromkeys([chart_timeframe, "5", "15", "60", "240", "30"]))
    for tf in tfs:
        rows = await candle_repo.get_by_symbol_and_timeframe(symbol, tf, 120)
        if len(rows) < 5:
            continue
        if tf == chart_timeframe:
            fallback = float(rows[-1].close)
        tf_ind = ind_svc.compute_from_ohlcv(
            [c.close for c in rows],
            [c.high for c in rows],
            [c.low for c in rows],
            [c.volume for c in rows],
        )
        indicators_by_tf[tf] = {
            k: float(v) for k, v in tf_ind.items() if isinstance(v, (int, float))
        }
    return await build_fresh_trade_plan(
        session,
        settings,
        symbol,
        indicators_by_tf,
        candle_fallback_close=fallback,
        chart_timeframe=chart_timeframe,
        run_ai=False,
    )
