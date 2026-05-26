"""Dashboard aggregate API for the web UI."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import BackgroundManagerDep, BotManagerDep, SessionDep, SettingsDep
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.timeframes import BYBIT_TIMEFRAME_LABELS, label_for_timeframe
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.candle_repo import CandleRepository
from app.db.repositories.order_repo import OrderRepository
from app.db.repositories.position_repo import PositionRepository
from app.db.repositories.risk_repo import RiskRepository
from app.db.repositories.market_change_repo import MarketChangeRepository
from app.db.repositories.signal_repo import SignalRepository
from app.db.repositories.strategy_decision_repo import StrategyDecisionRepository
from app.services.learning_service import LearningService
from app.services.market_analysis_service import MarketAnalysisService
from app.strategies.base import StrategyInputs
from app.exchanges.bybit_client import BybitClient
from app.exchanges.exchange_types import CandleData
from app.services.audit_service import AuditService
from app.services.indicator_service import IndicatorService
from app.services.live_price_service import fetch_display_price
from app.services.market_data_service import MarketDataService
from app.services.symbol_universe import resolve_dashboard_symbols
from app.services.trade_plan_service import build_fresh_trade_plan, build_quick_live_plan
from app.strategies.levels import apply_live_trade_levels
from app.utils.candles import filter_price_outliers
from app.utils.risk_labels import explain_risk_blocks

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _norm_candle_ts(ts: int) -> int:
    return ts // 1000 if ts > 1_000_000_000_000 else ts


def _build_candle_series(candles: list) -> list[dict]:
    """Sort, dedupe, and normalize timestamps for chart API."""
    by_time: dict[int, dict] = {}
    for c in candles:
        t = _norm_candle_ts(int(c.open_time))
        o, h, low, cl = float(c.open), float(c.high), float(c.low), float(c.close)
        if h < low or o <= 0 or cl <= 0:
            continue
        by_time[t] = {
            "time": t,
            "open": o,
            "high": max(h, o, cl),
            "low": min(low, o, cl),
            "close": cl,
            "volume": float(c.volume),
        }
    return [by_time[t] for t in sorted(by_time)]


@router.get("/meta")
async def dashboard_meta(settings: SettingsDep) -> dict:
    """Timeframes and labels for the UI."""
    symbols = await resolve_dashboard_symbols(settings)
    return {
        "timeframes": [
            {"code": tf, "label": label_for_timeframe(tf)} for tf in settings.timeframes
        ],
        "symbols": symbols,
        "symbol_count": len(symbols),
        "bot_trades_whitelist": settings.symbol_whitelist,
        "all_timeframe_labels": BYBIT_TIMEFRAME_LABELS,
    }


async def _resolve_display_price(
    symbol: str, settings: SettingsDep, candle_fallback: float = 0.0
) -> dict:
    info = await fetch_display_price(symbol, settings)
    if info.get("price", 0) <= 0 and candle_fallback > 0:
        info["price"] = candle_fallback
        info["source"] = "candle_close"
    return info


@router.get("/live-plan")
async def dashboard_live_plan(
    session: SessionDep,
    settings: SettingsDep,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("5"),
) -> dict:
    """Trade plan recalculated from current Bybit price (not stale DB entry)."""
    try:
        plan = await build_quick_live_plan(
            session, settings, symbol.upper(), chart_timeframe=timeframe
        )
    except Exception as exc:
        logger.warning("live_plan_failed", symbol=symbol, error=str(exc))
        return {"symbol": symbol.upper(), "plan": None, "error": str(exc)}
    if not plan:
        return {"symbol": symbol.upper(), "plan": None}
    return {"symbol": symbol.upper(), "plan": plan, "plan_symbol": plan.get("symbol")}


@router.get("/live-price")
async def dashboard_live_price(
    settings: SettingsDep,
    symbol: str = Query("BTCUSDT"),
) -> dict:
    """Display price = Bybit mainnet (same as TradingView BYBIT:*)."""
    symbol = symbol.upper()
    info = await fetch_display_price(symbol, settings)
    info["note_ru"] = _price_note_ru(settings, info)
    return info


def _price_note_ru(settings: Settings, info: dict) -> str:
    if not settings.use_bybit_market_data:
        return "Демо-данные, не Bybit."
    return (
        "Вход / SL / TP пересчитываются от текущей цены Bybit и ATR (5m). "
        "Не из старых записей в базе."
    )


async def _load_candles(
    symbol: str,
    timeframe: str,
    limit: int,
    session: SessionDep,
    settings: SettingsDep,
) -> tuple[list, str]:
    """DB first, then live Bybit fallback."""
    candle_repo = CandleRepository(session)
    rows = await candle_repo.get_by_symbol_and_timeframe(symbol, timeframe, limit)
    if len(rows) >= 5:
        return rows, "database"

    try:
        bybit = BybitClient(settings)
        live: list[CandleData] = await bybit.fetch_klines(symbol, timeframe, limit=limit)

        class _Row:
            pass

        adapted = []
        for c in live:
            r = _Row()
            r.open_time = c.open_time
            r.open = c.open
            r.high = c.high
            r.low = c.low
            r.close = c.close
            r.volume = c.volume
            adapted.append(r)
        return adapted, "bybit_live"
    except Exception as exc:
        logger.warning("bybit_live_candles_failed", error=str(exc))
        return rows, "empty"


@router.get("/overview")
async def dashboard_overview(
    session: SessionDep,
    settings: SettingsDep,
    manager: BotManagerDep,
    background: BackgroundManagerDep,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("5"),
    include_ratios: bool = Query(False),
) -> dict:
    try:
        symbol = symbol.upper()
        signal_repo = SignalRepository(session)
        risk_repo = RiskRepository(session)
        position_repo = PositionRepository(session)
        order_repo = OrderRepository(session)
        audit_repo = AuditRepository(session)
        change_repo = MarketChangeRepository(session)
        decision_repo = StrategyDecisionRepository(session)
        learning_svc = LearningService(session, AuditService(session))
        latest_signal = await signal_repo.get_latest(symbol)
        latest_decision = (await decision_repo.get_recent_by_symbol(symbol, 1)) or []
        latest_decision = latest_decision[0] if latest_decision else None
        candles, candle_source = await _load_candles(symbol, timeframe, 120, session, settings)
        ind_svc = IndicatorService(session, AuditService(session))
        if candles:
            indicators = ind_svc.compute_from_ohlcv(
                [c.close for c in candles],
                [c.high for c in candles],
                [c.low for c in candles],
                [c.volume for c in candles],
            )
        else:
            indicators = {}

        indicators_all_tf: dict[str, dict] = {}
        trader_briefing: dict | None = None
        candle_repo = CandleRepository(session)
        for tf in settings.dashboard_indicator_timeframes:
            tf_candles = await candle_repo.get_by_symbol_and_timeframe(symbol, tf, 120)
            if len(tf_candles) >= 5:
                tf_ind = ind_svc.compute_from_ohlcv(
                    [c.close for c in tf_candles],
                    [c.high for c in tf_candles],
                    [c.low for c in tf_candles],
                    [c.volume for c in tf_candles],
                )
                indicators_all_tf[tf] = {
                    k: float(v) for k, v in tf_ind.items() if isinstance(v, (int, float))
                }

        candle_close = float(candles[-1].close) if candles else 0.0
        try:
            fresh_plan = await build_fresh_trade_plan(
                session,
                settings,
                symbol,
                indicators_all_tf,
                candle_fallback_close=candle_close,
                chart_timeframe=timeframe,
            )
        except Exception as plan_exc:
            logger.warning("overview_trade_plan_failed", error=str(plan_exc))
            fresh_plan = {
                "action": "HOLD",
                "source": "error",
                "reason": str(plan_exc),
                "live_price": candle_close,
            }

        trader_briefing = None
        if indicators_all_tf and fresh_plan:
            from app.core.constants import SignalAction
            from app.strategies.base import StrategySignal

            analysis = MarketAnalysisService()
            pi = await _resolve_display_price(symbol, settings, candle_close)
            live_px = float(pi.get("price") or 0) or None
            inputs = StrategyInputs(
                symbol=symbol,
                timeframes=indicators_all_tf,
                regime=fresh_plan.get("regime") or (latest_decision.regime if latest_decision else None),
                live_price=live_px,
            )
            try:
                action_enum = SignalAction(fresh_plan.get("action") or "HOLD")
            except ValueError:
                action_enum = SignalAction.HOLD
            sig = StrategySignal(
                symbol=symbol,
                action=action_enum,
                confidence=float(fresh_plan.get("confidence") or 0),
                reason=fresh_plan.get("reason") or "",
                entry_price=fresh_plan.get("entry"),
                stop_loss=fresh_plan.get("stop_loss"),
                take_profit=fresh_plan.get("take_profit"),
            )
            apply_live_trade_levels(sig, live_px or 0, indicators_all_tf)
            trader_briefing = analysis.build_briefing(inputs, sig, live_price=live_px)

        price_info = await _resolve_display_price(symbol, settings, candle_close)

        return {
            "bot": {
                "running": manager.is_running,
                "last_run_at": manager.last_run_at,
                "last_error": manager.last_error,
                "trading_mode": settings.trading_mode.value,
                "live_enabled": settings.live_trading_enabled,
                "market_source": "bybit" if settings.use_bybit_market_data else "mock",
                "symbols": settings.symbol_whitelist,
                "timeframes": settings.timeframes,
                "timeframe_labels": {
                    tf: label_for_timeframe(tf) for tf in settings.timeframes
                },
                "kill_switch": settings.kill_switch,
                "background": background.status,
                "memory_enabled": settings.memory_enabled,
                "learning_enabled": settings.learning_enabled,
            },
            "tradingview": {
                "symbol": f"BYBIT:{symbol}",
                "interval": timeframe,
            },
            "market_changes": [
                {
                    "change_type": c.change_type,
                    "message": c.message,
                    "severity": c.severity,
                    "timeframe": c.timeframe,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in await change_repo.get_recent(symbol=symbol, limit=12)
            ],
            "learning": await learning_svc.get_summary(),
            "symbol": symbol,
            "timeframe": timeframe,
            "candle_source": candle_source,
            "last_price": price_info.get("price", 0),
            "price_source": price_info.get("source"),
            "price_info": price_info,
            "price_note": _price_note_ru(settings, price_info),
            "indicators": {
                k: float(v) for k, v in indicators.items() if isinstance(v, (int, float))
            },
            "indicators_all_timeframes": indicators_all_tf,
            "trader_briefing": trader_briefing,
            "trade_plan": fresh_plan,
            "signal": _signal_dict(latest_signal, latest_decision),
            "decision_journal": [
                _decision_dict(d) for d in await decision_repo.get_recent_by_symbol(symbol, 8)
            ],
            "last_cycle_decisions": _last_cycle_decisions(manager),
            "trading_params": {
                "position_size_mode": settings.position_size_mode,
                "order_usdt": settings.order_usdt,
                "entry_order_type": settings.entry_order_type,
                "max_risk_per_trade": settings.max_risk_per_trade,
                "paper_initial_balance": settings.paper_initial_balance,
            },
            "bot_activity": _bot_activity_for_symbol(manager, symbol),
            "risk_guide": _risk_guide_for_user(manager, symbol, settings.kill_switch),
            "risk_events": [
                {
                    "level": e.level,
                    "message": e.message,
                    "symbol": e.symbol,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in await risk_repo.get_recent_events(10)
            ],
            "positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "qty": p.qty,
                    "entry_price": p.entry_price,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "unrealized_pnl": p.unrealized_pnl,
                    "entry_explanation": p.entry_explanation,
                    "exit_explanation": p.exit_explanation,
                }
                for p in await position_repo.get_open_positions()
            ],
            "orders": [
                {
                    "order_id": o.order_id,
                    "symbol": o.symbol,
                    "side": o.side,
                    "status": o.status,
                    "qty": o.qty,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in await order_repo.get_recent(10)
            ],
            "audit": [
                {
                    "event_type": a.event_type,
                    "correlation_id": a.correlation_id,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in await audit_repo.get_recent(12)
            ],
            "last_cycle": manager.last_result,
        }
    except Exception as exc:
        logger.exception("dashboard_overview_failed")
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard error: {exc}. Run: alembic upgrade head or restart app (SQLite auto-creates tables).",
        ) from exc


@router.get("/chart")
async def chart_data(
    session: SessionDep,
    settings: SettingsDep,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("5"),
    limit: int = Query(150, le=500),
) -> dict:
    try:
        symbol = symbol.upper()
        signal_repo = SignalRepository(session)
        decision_repo = StrategyDecisionRepository(session)
        latest_decisions = await decision_repo.get_recent_by_symbol(symbol, 1)
        latest_decision = latest_decisions[0] if latest_decisions else None
        candles, candle_source = await _load_candles(symbol, timeframe, limit, session, settings)
        series = _build_candle_series(candles)
        series, candles_dropped = filter_price_outliers(series)
        ind_svc = IndicatorService(session, AuditService(session))
        if series:
            indicators = ind_svc.compute_from_ohlcv(
                [c["close"] for c in series],
                [c["high"] for c in series],
                [c["low"] for c in series],
                [c["volume"] for c in series],
            )
        else:
            indicators = {}
        indicators_by_tf: dict[str, dict] = {}
        if series:
            indicators_by_tf[timeframe] = {
                k: float(v) for k, v in indicators.items() if isinstance(v, (int, float))
            }
        candle_repo = CandleRepository(session)
        ind_svc = IndicatorService(session, AuditService(session))
        for tf in list(dict.fromkeys([timeframe, "5", "15", "30", "60", "240"])):
            if tf in indicators_by_tf:
                continue
            tf_rows = await candle_repo.get_by_symbol_and_timeframe(symbol, tf, 120)
            if len(tf_rows) >= 5:
                tf_ind = ind_svc.compute_from_ohlcv(
                    [c.close for c in tf_rows],
                    [c.high for c in tf_rows],
                    [c.low for c in tf_rows],
                    [c.volume for c in tf_rows],
                )
                indicators_by_tf[tf] = {
                    k: float(v) for k, v in tf_ind.items() if isinstance(v, (int, float))
                }

        candle_close = float(series[-1]["close"]) if series else (
            float(candles[-1].close) if candles else 0.0
        )
        try:
            trade_plan = await build_fresh_trade_plan(
                session,
                settings,
                symbol,
                indicators_by_tf,
                candle_fallback_close=candle_close,
                chart_timeframe=timeframe,
            )
        except Exception as plan_exc:
            logger.warning("chart_trade_plan_failed", error=str(plan_exc))
            trade_plan = {
                "action": "HOLD",
                "source": "error",
                "reason": str(plan_exc),
                "live_price": candle_close,
            }

        trade_levels: list[dict] = []
        level_specs: list[tuple[str, float | None, str, str]] = []
        if trade_plan and trade_plan.get("action") in ("BUY", "SELL"):
            level_specs = [
                ("Entry", trade_plan.get("entry"), "#2563eb", "solid"),
                ("Stop Loss", trade_plan.get("stop_loss"), "#dc2626", "dashed"),
                ("Take Profit", trade_plan.get("take_profit"), "#16a34a", "dashed"),
            ]

        for label, val, color, style in level_specs:
            if val is not None:
                trade_levels.append(
                    {
                        "name": label,
                        "price": float(val),
                        "color": color,
                        "lineStyle": style,
                    }
                )

        price_info = await _resolve_display_price(symbol, settings, candle_close)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timeframe_label": label_for_timeframe(timeframe),
            "tradingview_symbol": f"BYBIT:{symbol}",
            "candles": series,
            "candles_dropped": candles_dropped,
            "candle_source": candle_source,
            "last_price": price_info.get("price", 0),
            "price_source": price_info.get("source"),
            "price_info": price_info,
            "price_note": _price_note_ru(settings, price_info),
            "trade_levels": trade_levels,
            "trade_plan": trade_plan,
            "indicators": {
                k: float(v) for k, v in indicators.items() if isinstance(v, (int, float))
            },
            "market_source": "bybit" if settings.use_bybit_market_data else "mock",
        }
    except Exception as exc:
        logger.exception("dashboard_chart_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/refresh-market")
async def refresh_market(
    session: SessionDep,
    settings: SettingsDep,
    symbol: str | None = Query(None),
    timeframe: str | None = Query(None),
    full: bool = Query(False),
) -> dict:
    """Fast: symbol+timeframe only. Slow: full=true loads all pairs and TFs."""
    bybit = BybitClient(settings)
    audit = AuditService(session)
    repo = CandleRepository(session)
    svc = MarketDataService(bybit, repo, audit, settings)
    if full:
        counts = await svc.ingest_all()
        return {
            "ingested": counts,
            "source": "bybit",
            "mode": "full",
            "timeframes": settings.timeframes,
        }
    if symbol and timeframe:
        sym = symbol.upper()
        tfs = list(dict.fromkeys([timeframe, *settings.dashboard_indicator_timeframes]))
        counts: dict[str, int] = {}
        for tf in tfs:
            counts.update(await svc.ingest_symbol_tf(sym, tf))
        return {
            "ingested": counts,
            "source": "bybit",
            "mode": "symbol_mtf",
            "symbol": sym,
            "timeframes": tfs,
        }
    counts = await svc.ingest_cycle()
    return {
        "ingested": counts,
        "source": "bybit",
        "mode": "cycle",
        "timeframes": settings.bot_cycle_timeframes,
    }


def _signal_dict(signal, decision=None) -> dict | None:
    if not signal:
        return None
    explanation = (decision.explanation if decision else None) or signal.reason
    return {
        "action": signal.action,
        "confidence": signal.confidence,
        "reason": signal.reason,
        "explanation": explanation,
        "regime": decision.regime if decision else None,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "risk_reward_ratio": signal.risk_reward_ratio,
        "created_at": signal.created_at.isoformat() if signal.created_at else None,
    }


def _decision_dict(decision) -> dict:
    return {
        "action": decision.action,
        "confidence": decision.confidence,
        "regime": decision.regime,
        "reason": (decision.explanation or "")[:200],
        "explanation": decision.explanation,
        "created_at": decision.created_at.isoformat() if decision.created_at else None,
    }


def _last_cycle_decisions(manager) -> list[dict]:
    last = manager.last_result or {}
    out: list[dict] = []
    for d in last.get("decisions") or []:
        out.append(
            {
                "symbol": d.get("symbol"),
                "action": d.get("action"),
                "reason": d.get("reason"),
                "explanation": d.get("explanation"),
                "risk_allowed": d.get("risk_allowed"),
                "risk_blocks": d.get("risk_blocks"),
                "suggested_usdt": d.get("suggested_usdt"),
                "suggested_qty": d.get("suggested_qty"),
                "order": d.get("order"),
                "activity": d.get("activity"),
            }
        )
    return out


def _risk_guide_for_user(manager, symbol: str, kill_switch: bool = False) -> dict:
    """Plain-language risk status for the sidebar."""
    last = manager.last_result or {}
    sym = symbol.upper()
    row = next((d for d in (last.get("decisions") or []) if d.get("symbol") == sym), None)
    blocks = row.get("risk_blocks") if row else []
    explained = explain_risk_blocks(blocks or [])
    can_trade = bool(row and row.get("risk_allowed") and row.get("action") in ("BUY", "SELL"))
    return {
        "kill_switch_hint": "Аварийный выключатель: если ВКЛ — бот не откроет новые сделки (защита капитала).",
        "kill_switch_ok": not kill_switch,
        "last_action": row.get("action") if row else None,
        "can_trade_last_cycle": can_trade,
        "blocks": explained,
        "summary": _risk_summary_ru(explained, row),
    }


def _risk_summary_ru(explained: list[dict], row: dict | None) -> str:
    if not row:
        return "Запустите «Старт» или дождитесь цикла — здесь появится, почему сделка разрешена или нет."
    if row.get("risk_allowed") and row.get("order"):
        return "Последний цикл: сделка исполнена."
    if row.get("risk_allowed"):
        return f"Риск пройден ({row.get('action')}), но ордер не создан."
    if explained:
        return "Сделка заблокирована: " + explained[0]["text"]
    if row.get("action") == "HOLD":
        return "Сигнал HOLD — входа нет, это нормально."
    return "Проверьте журнал решений ниже."


def _bot_activity_for_symbol(manager, symbol: str) -> str | None:
    last = manager.last_result or {}
    for d in last.get("decisions") or []:
        if d.get("symbol") == symbol.upper():
            return d.get("activity")
    return None

