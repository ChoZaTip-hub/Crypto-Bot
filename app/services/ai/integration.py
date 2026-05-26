"""Attach AI analysis to plans and optionally influence signals."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.constants import SignalAction
from app.services.ai.trade_analyst import AiTradeAnalyst
from app.strategies.base import StrategyInputs, StrategySignal
from app.strategies.levels import apply_live_trade_levels


def apply_ai_influence_to_plan(
    plan: dict[str, Any],
    ai: dict[str, Any],
    settings: Settings,
    *,
    live_price: float,
    indicators_by_tf: dict[str, dict],
) -> dict[str, Any]:
    if not settings.ai_influence_trades or not ai.get("enabled"):
        return plan
    conf = float(ai.get("confidence") or 0)
    if conf < settings.ai_min_confidence_influence:
        plan["ai_influence_skipped"] = f"уверенность ИИ {conf:.0%} < {settings.ai_min_confidence_influence:.0%}"
        return plan
    action = str(ai.get("action", "HOLD")).upper()
    if action not in ("BUY", "SELL"):
        return plan

    rule_action = plan.get("action")
    chart_tf = str(ai.get("best_timeframe") or plan.get("horizon_tf") or "5")
    plan["action"] = action
    plan["confidence"] = conf
    plan["source"] = "ai_influenced"
    plan["reason"] = (
        f"ИИ ({conf:.0%}): {ai.get('summary_ru', '')[:120]} "
        f"[было {rule_action}]"
    )
    plan["entry"] = live_price
    plan["horizon_tf"] = chart_tf
    sig = StrategySignal(
        symbol=plan.get("symbol", ""),
        action=SignalAction.BUY if action == "BUY" else SignalAction.SELL,
        confidence=conf,
        reason=plan["reason"],
    )
    sig = apply_live_trade_levels(sig, live_price, indicators_by_tf, horizon_tf=chart_tf)
    plan["stop_loss"] = sig.stop_loss
    plan["take_profit"] = sig.take_profit
    plan["ai_influenced"] = True
    return plan


async def attach_ai_to_plan(
    plan: dict[str, Any],
    settings: Settings,
    *,
    symbol: str,
    live_price: float,
    chart_timeframe: str,
    regime: str | None,
    indicators_by_tf: dict[str, dict],
    setups: list[dict[str, Any]],
    candle_rows: list | None = None,
) -> dict[str, Any]:
    analyst = AiTradeAnalyst(settings)
    if not settings.ai_enabled:
        plan["ai"] = {"enabled": False, "hint": "AI_ENABLED=false в .env"}
        return plan

    chart_png: bytes | None = None
    if settings.ai_use_chart_image and candle_rows:
        from app.services.ai.chart_image import render_candles_png

        chart_png = render_candles_png(
            [float(c.close) for c in candle_rows[-80:]],
            highs=[float(c.high) for c in candle_rows[-80:]],
            lows=[float(c.low) for c in candle_rows[-80:]],
            title=f"{symbol} {chart_timeframe}",
        )

    ai = await analyst.analyze(
        symbol=symbol,
        live_price=live_price,
        chart_timeframe=chart_timeframe,
        regime=regime,
        setups=setups,
        rule_action=str(plan.get("action") or "HOLD"),
        rule_reason=str(plan.get("reason") or ""),
        indicators_by_tf=indicators_by_tf,
        chart_png=chart_png,
    )
    plan["ai"] = ai
    if settings.ai_influence_trades:
        plan = apply_ai_influence_to_plan(
            plan, ai, settings, live_price=live_price, indicators_by_tf=indicators_by_tf
        )
    return plan


async def apply_ai_to_signal(
    settings: Settings,
    inputs: StrategyInputs,
    signal: StrategySignal,
    *,
    chart_timeframe: str = "5",
) -> StrategySignal:
    if not settings.ai_influence_trades or not settings.ai_enabled:
        return signal
    from app.services.setup_scanner import scan_timeframe_setups

    analyst = AiTradeAnalyst(settings)
    if not analyst.available:
        return signal
    live = float(inputs.live_price or 0)
    if live <= 0:
        return signal
    setups = scan_timeframe_setups(inputs.symbol, inputs.timeframes, live)
    ai = await analyst.analyze(
        symbol=inputs.symbol,
        live_price=live,
        chart_timeframe=chart_timeframe,
        regime=inputs.regime,
        setups=setups,
        rule_action=signal.action.value,
        rule_reason=signal.reason or "",
        indicators_by_tf=inputs.timeframes,
    )
    conf = float(ai.get("confidence") or 0)
    if conf < settings.ai_min_confidence_influence:
        return signal
    action = str(ai.get("action", "HOLD")).upper()
    if action not in ("BUY", "SELL"):
        return signal
    signal.action = SignalAction.BUY if action == "BUY" else SignalAction.SELL
    signal.confidence = conf
    signal.reason = f"ИИ+правила: {ai.get('summary_ru', '')[:100]}"
    chart_tf = str(ai.get("best_timeframe") or chart_timeframe)
    return apply_live_trade_levels(signal, live, inputs.timeframes, horizon_tf=chart_tf)
