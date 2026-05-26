"""Human-readable risk block labels for the dashboard."""

RISK_BLOCK_RU: dict[str, str] = {
    "kill_switch_active": "Аварийный стоп включён — новые сделки запрещены",
    "circuit_breaker_drawdown": "Просадка портфеля слишком большая — торговля остановлена",
    "data_stale": "Свечи устарели (>2 мин) — бот не торгует, пока нет свежих данных Bybit",
    "volatility_too_high": "Волатильность выше лимита — вход отложен",
    "max_daily_loss_exceeded": "Дневной убыток достиг лимита — новые сделки запрещены",
    "max_open_positions": "Уже открыто максимум позиций — новый BUY нельзя",
    "max_exposure_per_symbol": "Слишком большая доля в одной монете",
    "mandatory_stop_loss_missing": "Нет Stop Loss — сделка не разрешена",
    "position_size_zero": "Размер позиции = 0 (проверьте сумму USDT и SL)",
    "position_already_open": "По этой монете позиция уже открыта — второй вход не делаем",
    "no_position_to_close": "Сигнал SELL, но позиции нет — закрывать нечего (шорт не включён)",
}


def explain_risk_blocks(blocks: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for code in blocks:
        out.append({"code": code, "text": RISK_BLOCK_RU.get(code, code)})
    return out
