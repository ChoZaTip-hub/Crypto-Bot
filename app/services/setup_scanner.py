"""Per-timeframe setup scan — where the bot sees a trade right now."""

from __future__ import annotations

from typing import Any

from app.core.timeframes import label_for_timeframe
from app.services.market_analysis_service import TF_WEIGHT, _bias_for_tf, _tf_tier
from app.strategies.levels import compute_sl_tp


def _coerce_live_entry(entry: float | None, live_price: float) -> float:
    if live_price <= 0:
        return float(entry or 0)
    if not entry or entry <= 0:
        return live_price
    drift = abs(entry - live_price) / live_price
    if drift > 0.08:
        return live_price
    return float(entry)


def scan_timeframe_setups(
    symbol: str,
    timeframes: dict[str, dict],
    live_price: float,
) -> list[dict[str, Any]]:
    """Immediate view: bullish/bearish bias per TF with entry=live price now."""
    setups: list[dict[str, Any]] = []
    if live_price <= 0:
        return setups

    for tf in sorted(timeframes.keys(), key=lambda x: (len(x), x)):
        ind = timeframes[tf] or {}
        close = float(ind.get("close") or 0)
        bias, reason = _bias_for_tf(ind)
        if bias == "neutral":
            continue
        action = "BUY" if bias == "bullish" else "SELL"
        atr = float(ind.get("atr") or 0)
        sl, tp = compute_sl_tp(action, live_price, atr)
        setups.append(
            {
                "symbol": symbol.upper(),
                "timeframe": tf,
                "label": label_for_timeframe(tf),
                "tier": _tf_tier(tf),
                "bias": bias,
                "action": action,
                "reason": reason,
                "entry": live_price,
                "stop_loss": sl,
                "take_profit": tp,
                "candle_close": close,
                "weight": TF_WEIGHT.get(tf, 1.0),
            }
        )
    setups.sort(key=lambda s: (-float(s["weight"]), s["timeframe"]))
    return setups


def pick_primary_setup(
    setups: list[dict[str, Any]],
    mtf_action: str,
) -> dict[str, Any] | None:
    if not setups:
        return None
    if mtf_action in ("BUY", "SELL"):
        for s in setups:
            if s["action"] == mtf_action:
                return s
    return setups[0]


def enrich_plan_with_setups(plan: dict[str, Any], setups: list[dict[str, Any]]) -> dict[str, Any]:
    plan = dict(plan)
    plan["setups"] = setups
    primary = pick_primary_setup(setups, str(plan.get("action") or "HOLD"))
    plan["primary_setup"] = primary
    if primary:
        plan["setup_timeframe"] = primary["timeframe"]
        plan["setup_timeframe_label"] = primary["label"]
    live = float(plan.get("live_price") or 0)
    if plan.get("entry") is not None:
        plan["entry"] = _coerce_live_entry(plan.get("entry"), live)
    if setups:
        lines = [
            f"{s['label']}: {s['action']} — {s['reason'][:60]}"
            for s in setups[:6]
        ]
        plan["setups_summary"] = " · ".join(lines)
    return plan
