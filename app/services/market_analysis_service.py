"""Multi-timeframe market study and trader-style briefing (no TradingView license)."""

from __future__ import annotations

from typing import Any

from app.core.constants import SignalAction
from app.core.timeframes import label_for_timeframe
from app.strategies.base import StrategyInputs, StrategySignal

TF_WEIGHT: dict[str, float] = {
    "1": 0.6,
    "3": 0.7,
    "5": 1.0,
    "15": 1.4,
    "30": 1.6,
    "60": 2.0,
    "120": 2.2,
    "240": 2.5,
    "D": 2.8,
    "W": 3.0,
    "M": 3.2,
}

# Top-down analysis: старшие ТФ — направление, младшие — вход
TF_TIER_HIGHER = frozenset({"120", "240", "360", "720", "D", "W", "M"})
TF_TIER_MID = frozenset({"30", "60"})
TF_TIER_LOWER = frozenset({"1", "3", "5", "15"})


def _tf_tier(tf: str) -> str:
    if tf in TF_TIER_HIGHER:
        return "higher"
    if tf in TF_TIER_MID:
        return "mid"
    if tf in TF_TIER_LOWER:
        return "lower"
    return "mid"


def _tier_edge(per_tf: list[dict[str, Any]], tier: str) -> float:
    bull = bear = 0.0
    for row in per_tf:
        if row.get("tier") != tier:
            continue
        w = float(row.get("weight") or 1)
        if row.get("bias") == "bullish":
            bull += w
        elif row.get("bias") == "bearish":
            bear += w
    return bull - bear


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.2f}"


def _tf_weight(tf: str) -> float:
    return TF_WEIGHT.get(tf, 1.0)


def _bias_for_tf(ind: dict[str, Any]) -> tuple[str, str]:
    """Return bullish | bearish | neutral and short reason."""
    close = float(ind.get("close") or 0)
    if close <= 0:
        return "neutral", "нет данных"
    ema = float(ind.get("ema") or close)
    rsi = float(ind.get("rsi") or 50)
    adx = float(ind.get("adx") or 0)
    bb_lower = ind.get("bb_lower")
    bb_upper = ind.get("bb_upper")

    score = 0
    parts: list[str] = []

    if close > ema * 1.001:
        score += 1
        parts.append("цена выше EMA")
    elif close < ema * 0.999:
        score -= 1
        parts.append("цена ниже EMA")

    if rsi > 58:
        score -= 1
        parts.append(f"RSI перекуплен ({rsi:.0f})")
    elif rsi < 42:
        score += 1
        parts.append(f"RSI перепродан ({rsi:.0f})")
    elif rsi > 52:
        score += 1
        parts.append(f"RSI бычий ({rsi:.0f})")
    elif rsi < 48:
        score -= 1
        parts.append(f"RSI медвежий ({rsi:.0f})")

    if adx > 22:
        if close > ema:
            score += 1
            parts.append(f"тренд вверх ADX={adx:.0f}")
        elif close < ema:
            score -= 1
            parts.append(f"тренд вниз ADX={adx:.0f}")

    if bb_lower is not None and bb_upper is not None:
        bl, bu = float(bb_lower), float(bb_upper)
        if close <= bl * 1.002:
            score += 1
            parts.append("у нижней BB")
        elif close >= bu * 0.998:
            score -= 1
            parts.append("у верхней BB")

    if score >= 1:
        return "bullish", "; ".join(parts) or "бычий уклон"
    if score <= -1:
        return "bearish", "; ".join(parts) or "медвежий уклон"
    return "neutral", "; ".join(parts) if parts else "без явного уклона"


def _pnl_pct(entry: float, target: float, is_long: bool) -> float | None:
    if not entry or not target:
        return None
    if is_long:
        return (target - entry) / entry * 100
    return (entry - target) / entry * 100


class MarketAnalysisService:
    """Rule-based chart study — same data the bot uses, explained like a trader."""

    def build_briefing(
        self,
        inputs: StrategyInputs,
        signal: StrategySignal,
        *,
        live_price: float | None = None,
    ) -> dict[str, Any]:
        per_tf: list[dict[str, Any]] = []
        bull_w = bear_w = 0.0
        mark = live_price or inputs.live_price

        for tf in sorted(inputs.timeframes.keys(), key=lambda x: (len(x), x)):
            ind = inputs.timeframes[tf]
            if not ind:
                continue
            bias, reason = _bias_for_tf(ind)
            w = _tf_weight(tf)
            tier = _tf_tier(tf)
            if bias == "bullish":
                bull_w += w
            elif bias == "bearish":
                bear_w += w
            bar_close = float(ind.get("close") or 0)
            per_tf.append(
                {
                    "timeframe": tf,
                    "label": label_for_timeframe(tf),
                    "tier": tier,
                    "bias": bias,
                    "weight": w,
                    "reason": reason,
                    "close": bar_close,
                    "live_price": mark,
                    "rsi": float(ind.get("rsi")) if ind.get("rsi") is not None else None,
                    "adx": float(ind.get("adx")) if ind.get("adx") is not None else None,
                    "ema": float(ind.get("ema")) if ind.get("ema") is not None else None,
                }
            )

        edge = bull_w - bear_w
        h_edge = _tier_edge(per_tf, "higher")
        m_edge = _tier_edge(per_tf, "mid")
        l_edge = _tier_edge(per_tf, "lower")

        mtf_verdict, mtf_text = self._top_down_verdict(h_edge, m_edge, l_edge, bull_w, bear_w, edge)

        action = signal.action.value if isinstance(signal.action, SignalAction) else str(signal.action)
        is_long = action == "BUY"
        # Entry/SL/TP — из последнего сигнала/позиции бота; mark — только «сейчас на рынке»
        if signal.entry_price is not None and float(signal.entry_price) > 0:
            entry = float(signal.entry_price)
        elif action in ("BUY", "SELL") and mark:
            entry = float(mark)
        else:
            entry = 0.0
        sl = float(signal.stop_loss) if signal.stop_loss else None
        tp = float(signal.take_profit) if signal.take_profit else None

        trade_block: dict[str, Any] = {
            "action": action,
            "confidence_pct": round(signal.confidence * 100, 1),
            "entry": entry or None,
            "current_price": mark,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": signal.risk_reward_ratio,
        }
        if entry and sl and tp:
            trade_block["risk_pct"] = round(abs(_pnl_pct(entry, sl, is_long) or 0), 2)
            trade_block["reward_pct"] = round(abs(_pnl_pct(entry, tp, is_long) or 0), 2)
            trade_block["reward_pct_signed"] = round(_pnl_pct(entry, tp, is_long) or 0, 2)
            trade_block["risk_pct_signed"] = round(_pnl_pct(entry, sl, is_long) or 0, 2)

        regime = inputs.regime or "unknown"
        headline = self._headline(action, signal.confidence, regime, mtf_verdict, edge)

        return {
            "symbol": inputs.symbol,
            "regime": regime,
            "live_price": mark,
            "headline": headline,
            "mtf_verdict": mtf_verdict,
            "mtf_summary": mtf_text,
            "confluence": {
                "bullish_weight": round(bull_w, 2),
                "bearish_weight": round(bear_w, 2),
                "edge": round(edge, 2),
                "higher_edge": round(h_edge, 2),
                "mid_edge": round(m_edge, 2),
                "lower_edge": round(l_edge, 2),
            },
            "timeframes": per_tf,
            "trade": trade_block,
            "data_note": (
                "Вход / SL / TP — от текущей цены Bybit и ATR (5m), обновляются каждые 2 с. "
                "По ТФ в таблице — закрытие последней свечи."
            ),
        }

    def _top_down_verdict(
        self,
        h_edge: float,
        m_edge: float,
        l_edge: float,
        bull_w: float,
        bear_w: float,
        edge: float,
    ) -> tuple[str, str]:
        """Top-down: старшие ТФ задают bias, младшие — подтверждение входа."""
        if h_edge >= 1.5 and l_edge >= 0:
            return "bullish", (
                f"Top-down бычий: старшие ТФ +{h_edge:.1f}, младшие {l_edge:+.1f} "
                f"(всего бычьих {bull_w:.1f} vs {bear_w:.1f})."
            )
        if h_edge <= -1.5 and l_edge <= 0:
            return "bearish", (
                f"Top-down медвежий: старшие {h_edge:.1f}, младшие {l_edge:+.1f} "
                f"(медвежьих {bear_w:.1f} vs бычьих {bull_w:.1f})."
            )
        if h_edge >= 1.5 and l_edge < -0.5:
            return "mixed", (
                f"Старшие ТФ бычьи (+{h_edge:.1f}), но младшие против ({l_edge:+.1f}) — "
                "ждать откат или подтверждение на 5m/15m."
            )
        if h_edge <= -1.5 and l_edge > 0.5:
            return "mixed", (
                f"Старшие ТФ медвежьи ({h_edge:.1f}), младшие ещё растут ({l_edge:+.1f}) — "
                "возможен отскок, осторожно с шортом."
            )
        if edge >= 2:
            return "bullish", f"Общий бычий консенсус ({bull_w:.1f} vs {bear_w:.1f})."
        if edge <= -2:
            return "bearish", f"Общий медвежий консенсус ({bear_w:.1f} vs {bull_w:.1f})."
        return "mixed", f"ТФ расходятся: старшие {h_edge:+.1f}, средние {m_edge:+.1f}, младшие {l_edge:+.1f}."

    def _headline(
        self,
        action: str,
        confidence: float,
        regime: str,
        mtf_verdict: str,
        edge: float,
    ) -> str:
        if action == "HOLD":
            return (
                "Сейчас без сделки: сигнал HOLD — ждём согласованности ТФ или лучшей точки входа."
            )
        align = (
            (action == "BUY" and mtf_verdict == "bullish")
            or (action == "SELL" and mtf_verdict == "bearish")
        )
        if align:
            return (
                f"Рекомендация {action}: уверенность {confidence * 100:.0f}%, "
                f"режим «{regime}», таймфреймы поддерживают идею (edge={edge:+.1f})."
            )
        if mtf_verdict == "mixed":
            return (
                f"Сигнал {action} ({confidence * 100:.0f}%), но ТФ спорят — "
                "размер позиции ограничен риском, возможен отказ."
            )
        return (
            f"Сигнал {action} ({confidence * 100:.0f}%) против старшего уклона ТФ — "
            "осторожный вход или ожидание."
        )

    def format_briefing_text(self, briefing: dict[str, Any]) -> str:
        lines = [
            f"▸ {briefing.get('headline', '')}",
            "",
            f"Режим: {briefing.get('regime', '—')}",
            briefing.get("mtf_summary", ""),
            "",
            "Разбор по таймфреймам:",
        ]
        if briefing.get("live_price"):
            lines.append(f"  Текущая цена (Bybit): {_fmt(briefing['live_price'])}")
            lines.append("")
        for row in briefing.get("timeframes") or []:
            bias_ru = {"bullish": "↑ бычий", "bearish": "↓ медвежий", "neutral": "→ нейтр."}.get(
                row.get("bias", ""), row.get("bias", "")
            )
            tier_ru = {"higher": "старший", "mid": "средний", "lower": "младший"}.get(
                row.get("tier", ""), ""
            )
            lines.append(
                f"  • [{tier_ru}] {row.get('label')}: {bias_ru} — {row.get('reason', '')} "
                f"(свеча {_fmt(row.get('close'))})"
            )
        conf = briefing.get("confluence") or {}
        if conf.get("higher_edge") is not None:
            lines.extend(
                [
                    "",
                    "Top-down:",
                    f"  Старшие ТФ edge={conf.get('higher_edge'):+.1f}, "
                    f"средние={conf.get('mid_edge'):+.1f}, младшие={conf.get('lower_edge'):+.1f}",
                ]
            )
        trade = briefing.get("trade") or {}
        if trade.get("action") not in (None, "HOLD"):
            lines.extend(
                [
                    "",
                    "План сделки:",
                    f"  Вход: {_fmt(trade.get('entry'))}",
                    f"  Stop Loss: {_fmt(trade.get('stop_loss'))} "
                    f"({trade.get('risk_pct_signed', trade.get('risk_pct', '—'))}%)",
                    f"  Take Profit: {_fmt(trade.get('take_profit'))} "
                    f"(+{trade.get('reward_pct_signed', trade.get('reward_pct', '—'))}%)",
                ]
            )
            if trade.get("risk_reward"):
                lines.append(f"  Risk/Reward: {trade['risk_reward']:.2f}")
        lines.extend(["", briefing.get("data_note", "")])
        return "\n".join(lines)
