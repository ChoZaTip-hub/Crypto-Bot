"""Live entry / SL / TP from current price and ATR (intraday horizon)."""

from app.core.constants import SignalAction
from app.strategies.base import StrategySignal


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


def compute_sl_tp(action: str | SignalAction, live_price: float, atr: float) -> tuple[float | None, float | None]:
    if live_price <= 0 or atr <= 0:
        return None, None
    act = action.value if isinstance(action, SignalAction) else str(action)
    if act == "BUY":
        return live_price - 2 * atr, live_price + 3 * atr
    if act == "SELL":
        return live_price + 2 * atr, live_price - 3 * atr
    return None, None


def apply_live_trade_levels(
    signal: StrategySignal,
    live_price: float,
    timeframes: dict[str, dict],
    *,
    horizon_tf: str = "5",
) -> StrategySignal:
    """Entry = current market; SL/TP from ATR on chart TF (fallback 5m)."""
    if signal.action == SignalAction.HOLD or live_price <= 0:
        return signal
    atr = pick_atr(timeframes, prefer_tf=horizon_tf)
    signal.entry_price = live_price
    sl, tp = compute_sl_tp(signal.action, live_price, atr)
    signal.stop_loss = sl
    signal.take_profit = tp
    if sl and tp and live_price:
        risk = abs(live_price - sl)
        reward = abs(tp - live_price)
        signal.risk_reward_ratio = reward / risk if risk > 0 else None
    signal.timeframe_confirmations = {
        **(signal.timeframe_confirmations or {}),
        "entry_horizon_tf": horizon_tf,
    }
    return signal
