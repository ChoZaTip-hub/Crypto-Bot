"""Live entry / SL / TP from current price and ATR (intraday horizon)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.constants import SignalAction
from app.strategies.base import StrategySignal

if TYPE_CHECKING:
    from app.core.config import Settings


@dataclass(frozen=True)
class SlTpMultipliers:
    """ATR multiples for stop and target (reward / risk = tp_atr / sl_atr when enforced)."""

    sl_atr: float = 1.5
    tp_atr: float = 4.5
    min_rr: float = 2.0

    @classmethod
    def from_settings(cls, settings: Settings) -> SlTpMultipliers:
        return cls(
            sl_atr=float(settings.sl_atr_multiplier),
            tp_atr=float(settings.tp_atr_multiplier),
            min_rr=float(settings.min_risk_reward_ratio),
        )


DEFAULT_SL_TP = SlTpMultipliers()


def pick_atr(timeframes: dict[str, dict], prefer_tf: str | None = None) -> float:
    order: list[str] = []
    if prefer_tf:
        order.append(prefer_tf)
    order.extend(["5", "15", "60", "240", "30"])
    seen: set[str] = set()
    for tf in order:
        if tf in seen:
            continue
        seen.add(tf)
        ind = timeframes.get(tf) or {}
        atr = float(ind.get("atr") or 0)
        if atr > 0:
            return atr
    return 0.0


def compute_sl_tp(
    action: str | SignalAction,
    live_price: float,
    atr: float,
    *,
    mults: SlTpMultipliers | None = None,
) -> tuple[float | None, float | None]:
    """SL/TP from ATR; enforces minimum risk:reward (default 1:2, target 1:3)."""
    if live_price <= 0 or atr <= 0:
        return None, None
    m = mults or DEFAULT_SL_TP
    act = action.value if isinstance(action, SignalAction) else str(action)
    if act == "BUY":
        sl = live_price - m.sl_atr * atr
        tp = live_price + m.tp_atr * atr
    elif act == "SELL":
        sl = live_price + m.sl_atr * atr
        tp = live_price - m.tp_atr * atr
    else:
        return None, None

    risk = abs(live_price - sl)
    reward = abs(tp - live_price)
    if risk > 0 and m.min_rr > 0 and reward / risk < m.min_rr:
        if act == "BUY":
            tp = live_price + risk * m.min_rr
        else:
            tp = live_price - risk * m.min_rr
    return sl, tp


def risk_reward_ratio(
    entry: float,
    sl: float | None,
    tp: float | None,
) -> float | None:
    if not sl or not tp or entry <= 0:
        return None
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    return reward / risk if risk > 0 else None


def estimate_fixed_usdt_pnl(
    entry: float,
    sl: float | None,
    tp: float | None,
    order_usdt: float,
) -> dict[str, float | None]:
    """Approx. loss/gain at SL/TP for fixed-USDT position size."""
    if entry <= 0 or order_usdt <= 0 or not sl or not tp:
        return {}
    qty = order_usdt / entry
    risk_usdt = qty * abs(entry - sl)
    reward_usdt = qty * abs(tp - entry)
    rr = reward_usdt / risk_usdt if risk_usdt > 0 else None
    return {
        "risk_usdt": round(risk_usdt, 2),
        "reward_usdt": round(reward_usdt, 2),
        "risk_reward_ratio": round(rr, 2) if rr is not None else None,
    }


def apply_live_trade_levels(
    signal: StrategySignal,
    live_price: float,
    timeframes: dict[str, dict],
    *,
    horizon_tf: str = "5",
    mults: SlTpMultipliers | None = None,
) -> StrategySignal:
    """Entry = current market; SL/TP from ATR on chart TF (fallback 5m)."""
    if signal.action == SignalAction.HOLD or live_price <= 0:
        return signal
    atr = pick_atr(timeframes, prefer_tf=horizon_tf)
    signal.entry_price = live_price
    sl, tp = compute_sl_tp(signal.action, live_price, atr, mults=mults)
    signal.stop_loss = sl
    signal.take_profit = tp
    signal.risk_reward_ratio = risk_reward_ratio(live_price, sl, tp)
    existing = signal.timeframe_confirmations
    if isinstance(existing, dict):
        merged = {**existing, "entry_horizon_tf": horizon_tf}
        signal.timeframe_confirmations = list(merged.keys())
    else:
        tfc = list(existing or [])
        tag = f"horizon:{horizon_tf}"
        if tag not in tfc:
            tfc.append(tag)
        signal.timeframe_confirmations = tfc
    return signal
