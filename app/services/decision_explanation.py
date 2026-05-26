"""Human-readable trade decision explanations (Russian)."""

from __future__ import annotations

from typing import Any

from app.core.constants import SignalAction
from app.core.timeframes import label_for_timeframe
from app.risk.manager import RiskAssessment
from app.strategies.base import StrategyInputs, StrategySignal

REGIME_LABELS = {
    "trending": "Трендовый рынок",
    "ranging": "Боковик (флэт)",
    "unknown": "Неопределённый режим",
}

REGIME_RULES = {
    "trending": "ADX(1h) > 25 — сильное направленное движение. Бот использует трендовую стратегию (EMA + ADX).",
    "ranging": "ADX(1h) < 20 и узкие полосы Боллинджера — цена в диапазоне. Бот использует возврат к среднему (RSI + BB).",
    "unknown": "Сигналы тренда и флэта неоднозначны — бот сверяет обе стратегии и взвешивает голоса.",
}

STRATEGY_LABELS = {
    "trend": "Тренд (EMA + ADX)",
    "mean_reversion": "Возврат к среднему (RSI + Bollinger)",
    "multi_timeframe": "Мульти-таймфрейм",
}

EXIT_REASON_LABELS = {
    "stop_loss": "Stop Loss",
    "take_profit": "Take Profit",
    "manual": "Ручное закрытие",
    "signal_sell": "Сигнал на выход",
}


def _fmt_price(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.2f}"


def _action_label(action: SignalAction | str) -> str:
    val = action.value if isinstance(action, SignalAction) else str(action).upper()
    return {"BUY": "ПОКУПКА", "SELL": "ПРОДАЖА", "HOLD": "ОЖИДАНИЕ"}.get(val, val)


def _indicator_lines(inputs: StrategyInputs, timeframes: list[str] | None = None) -> list[str]:
    lines: list[str] = []
    tfs = timeframes or sorted(inputs.timeframes.keys(), key=lambda x: (len(x), x))
    for tf in tfs:
        ind = inputs.timeframes.get(tf) or {}
        if not ind:
            continue
        lbl = label_for_timeframe(tf)
        parts: list[str] = []
        if "close" in ind:
            parts.append(f"цена={_fmt_price(ind['close'])}")
        if "rsi" in ind:
            parts.append(f"RSI={ind['rsi']:.1f}")
        if "ema" in ind:
            parts.append(f"EMA={_fmt_price(ind['ema'])}")
        if "adx" in ind:
            parts.append(f"ADX={ind['adx']:.1f}")
        if "atr" in ind:
            parts.append(f"ATR={_fmt_price(ind['atr'])}")
        if "bb_lower" in ind and "bb_upper" in ind:
            parts.append(f"BB={_fmt_price(ind['bb_lower'])}–{_fmt_price(ind['bb_upper'])}")
        if parts:
            lines.append(f"  • {lbl}: " + ", ".join(parts))
    return lines


def build_entry_explanation(
    inputs: StrategyInputs,
    signal: StrategySignal,
    sub_signals: list[StrategySignal],
    *,
    active_strategies: list[str] | None = None,
    risk: RiskAssessment | None = None,
) -> str:
    """Full explanation for entry / hold / blocked entry."""
    regime = inputs.regime or "unknown"
    lines: list[str] = [
        f"═══ Решение: {_action_label(signal.action)} {inputs.symbol} ═══",
        "",
        f"📊 Ситуация на рынке: {REGIME_LABELS.get(regime, regime)}",
        REGIME_RULES.get(regime, ""),
        "",
        "📈 Индикаторы:",
    ]
    lines.extend(_indicator_lines(inputs) or ["  • Недостаточно данных по свечам"])
    lines.append("")

    active = active_strategies or [s.strategy_name for s in sub_signals if s.strategy_name]
    if active:
        names = ", ".join(STRATEGY_LABELS.get(n, n) for n in active)
        lines.append(f"🧠 Активные стратегии: {names}")
        lines.append("")

    if sub_signals:
        lines.append("🔍 Голоса подстратегий:")
        for sub in sub_signals:
            label = STRATEGY_LABELS.get(sub.strategy_name, sub.strategy_name)
            lines.append(
                f"  • {label}: {_action_label(sub.action)} "
                f"({sub.confidence * 100:.0f}% уверенности) — {sub.reason}"
            )
        lines.append("")

    if inputs.learning_weights:
        w_parts = [f"{k}={v:.2f}" for k, v in sorted(inputs.learning_weights.items())]
        lines.append(f"📚 Обучение (веса): {', '.join(w_parts)}")
        lines.append("")

    recent = inputs.memory_context.get("recent_changes") or []
    if recent:
        lines.append(f"💾 Память: зафиксировано {len(recent)} изменений индикаторов/цены")
        for ch in recent[:3]:
            msg = ch.get("message") if isinstance(ch, dict) else str(ch)
            if msg:
                lines.append(f"  • {msg}")
        lines.append("")

    lines.append(f"✅ Итог: {_action_label(signal.action)} с уверенностью {signal.confidence * 100:.0f}%")
    if signal.action != SignalAction.HOLD:
        lines.append(f"   Вход: {_fmt_price(signal.entry_price)}")
        lines.append(f"   Stop Loss: {_fmt_price(signal.stop_loss)}")
        lines.append(f"   Take Profit: {_fmt_price(signal.take_profit)}")
        if signal.risk_reward_ratio:
            lines.append(f"   Risk/Reward: {signal.risk_reward_ratio:.2f}")
        lines.append(f"   Кратко: {signal.reason}")
    else:
        lines.append(f"   Почему без сделки: {signal.reason}")

    if risk is not None:
        lines.append("")
        if risk.allowed:
            lines.append(f"🛡 Риск: разрешено, объём ≈ {risk.suggested_qty:.6f}")
        else:
            blocks = ", ".join(risk.blocks) if risk.blocks else "неизвестно"
            lines.append(f"🛡 Риск: ЗАБЛОКИРОВАНО ({blocks})")

    return "\n".join(lines)


def build_exit_explanation(
    *,
    symbol: str,
    side: str,
    entry_price: float,
    exit_price: float,
    exit_reason: str,
    trigger_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    entry_explanation: str | None = None,
) -> str:
    """Explanation when closing a position (SL/TP/manual)."""
    is_long = side.lower() in ("buy", "long")
    if is_long:
        pnl_pct = (exit_price - entry_price) / entry_price * 100 if entry_price else 0.0
    else:
        pnl_pct = (entry_price - exit_price) / entry_price * 100 if entry_price else 0.0

    reason_lbl = EXIT_REASON_LABELS.get(exit_reason, exit_reason)
    lines = [
        f"═══ Выход из сделки: {symbol} ═══",
        "",
        f"📤 Причина выхода: {reason_lbl}",
    ]

    if exit_reason == "stop_loss" and stop_loss is not None:
        lines.append(
            f"   Цена { _fmt_price(trigger_price or exit_price) } достигла Stop Loss "
            f"{_fmt_price(stop_loss)} — ограничение убытка."
        )
    elif exit_reason == "take_profit" and take_profit is not None:
        lines.append(
            f"   Цена {_fmt_price(trigger_price or exit_price)} достигла Take Profit "
            f"{_fmt_price(take_profit)} — фиксация прибыли."
        )
    elif exit_reason == "manual":
        lines.append("   Позиция закрыта вручную через API или панель.")
    else:
        lines.append(f"   Триггер по цене: {_fmt_price(trigger_price or exit_price)}")

    lines.extend(
        [
            "",
            f"📊 Вход: {_fmt_price(entry_price)} → Выход: {_fmt_price(exit_price)}",
            f"   Результат: {pnl_pct:+.2f}%",
            f"   Направление: {'LONG' if is_long else 'SHORT'}",
        ]
    )

    if entry_explanation:
        lines.extend(["", "📥 Почему был вход:", entry_explanation.strip()])

    return "\n".join(lines)


def short_summary(explanation: str, max_len: int = 160) -> str:
    """One-line summary for signal.reason field."""
    for line in explanation.splitlines():
        line = line.strip()
        if line.startswith("✅ Итог:"):
            line = line.replace("✅ Итог:", "Итог:", 1).strip()
            return line[: max_len - 3] + "..." if len(line) > max_len else line
    for line in explanation.splitlines():
        line = line.strip()
        if line and not line.startswith("═") and not line.startswith("📊") and not line.startswith("📈"):
            return line[: max_len - 3] + "..." if len(line) > max_len else line
    return explanation[:max_len]
