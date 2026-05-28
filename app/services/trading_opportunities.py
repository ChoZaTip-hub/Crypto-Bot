"""Rank coins from scanner + last bot cycle for dashboard chart focus."""

from __future__ import annotations

from typing import Any

from app.services.trading_universe_service import TradingUniverseService


def build_trading_opportunities(last_result: dict | None) -> dict[str, Any]:
    """Merge scanner ranks and per-symbol cycle decisions into chart picks."""
    last = last_result or {}
    scanner = last.get("scanner") or {}
    ranked: list[dict] = list(scanner.get("ranked") or [])
    scanner_top: list[str] = list(scanner.get("top_symbols") or [])

    if not ranked:
        snap = TradingUniverseService.last_scan_snapshot()
        if snap:
            ranked = [
                {
                    "symbol": r.symbol,
                    "score": r.score,
                    "action": r.action,
                    "reason": (r.reason or "")[:120],
                }
                for r in snap.ranked[:20]
            ]
            scanner_top = list(snap.top_symbols)

    by_symbol: dict[str, dict[str, Any]] = {}
    for row in ranked:
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            continue
        by_symbol[sym] = {
            "symbol": sym,
            "score": float(row.get("score") or 0),
            "action": row.get("action") or "HOLD",
            "reason": row.get("reason") or "",
            "source": "scanner",
        }

    for d in last.get("decisions") or []:
        sym = str(d.get("symbol") or "").upper()
        if not sym:
            continue
        entry = by_symbol.get(sym) or {"symbol": sym, "score": 0.0, "action": "HOLD"}
        action = d.get("action") or entry.get("action") or "HOLD"
        conf = float(d.get("confidence") or 0)
        entry["action"] = action
        entry["confidence"] = conf
        entry["risk_allowed"] = d.get("risk_allowed")
        entry["executed"] = bool(d.get("orders") or d.get("order"))
        entry["activity"] = d.get("activity")
        entry["reason"] = (d.get("reason") or entry.get("reason") or "")[:200]
        if action in ("BUY", "SELL"):
            entry["score"] = max(float(entry.get("score") or 0), conf * 50.0)
            entry["source"] = "bot_cycle"
        if entry.get("executed"):
            entry["score"] = max(float(entry.get("score") or 0), 1000.0)
        by_symbol[sym] = entry

    picks = sorted(by_symbol.values(), key=lambda x: -float(x.get("score") or 0))

    recommended: str | None = None
    for p in picks:
        if p.get("executed"):
            recommended = p["symbol"]
            break
    if not recommended:
        for p in picks:
            if p.get("action") in ("BUY", "SELL") and p.get("risk_allowed"):
                recommended = p["symbol"]
                break
    if not recommended:
        for p in picks:
            if p.get("action") in ("BUY", "SELL"):
                recommended = p["symbol"]
                break
    if not recommended and picks:
        recommended = picks[0]["symbol"]
    if not recommended and scanner_top:
        recommended = str(scanner_top[0]).upper()

    return {
        "picks": picks[:15],
        "recommended_chart_symbol": recommended,
        "scanner_top": scanner_top,
        "trading_universe": list(last.get("trading_universe") or []),
    }
