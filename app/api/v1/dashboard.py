"""Dashboard aggregate API for the web UI."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import BackgroundManagerDep, BotManagerDep, SessionDep, SettingsDep
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
from app.services.market_data_service import MarketDataService
from app.utils.candles import filter_price_outliers

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
    return {
        "timeframes": [
            {"code": tf, "label": label_for_timeframe(tf)} for tf in settings.timeframes
        ],
        "symbols": settings.symbol_whitelist,
        "all_timeframe_labels": BYBIT_TIMEFRAME_LABELS,
    }


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

        if indicators_all_tf:
            from app.core.constants import SignalAction
            from app.strategies.base import StrategySignal

            analysis = MarketAnalysisService()
            action_enum = SignalAction.HOLD
            if latest_signal:
                try:
                    action_enum = SignalAction(latest_signal.action)
                except ValueError:
                    pass
            inputs = StrategyInputs(
                symbol=symbol,
                timeframes=indicators_all_tf,
                regime=latest_decision.regime if latest_decision else None,
            )
            sig = StrategySignal(
                symbol=symbol,
                action=action_enum,
                confidence=latest_signal.confidence if latest_signal else 0.0,
                reason=latest_signal.reason if latest_signal else "",
                entry_price=latest_signal.entry_price if latest_signal else None,
                stop_loss=latest_signal.stop_loss if latest_signal else None,
                take_profit=latest_signal.take_profit if latest_signal else None,
                risk_reward_ratio=latest_signal.risk_reward_ratio if latest_signal else None,
            )
            open_positions = await position_repo.get_open_positions()
            pos = next((p for p in open_positions if p.symbol == symbol), None)
            if pos:
                sig.action = SignalAction.BUY
                sig.entry_price = pos.entry_price
                sig.stop_loss = pos.stop_loss
                sig.take_profit = pos.take_profit
            trader_briefing = analysis.build_briefing(inputs, sig)

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
            "last_price": float(candles[-1].close) if candles else 0,
            "indicators": {
                k: float(v) for k, v in indicators.items() if isinstance(v, (int, float))
            },
            "indicators_all_timeframes": indicators_all_tf,
            "trader_briefing": trader_briefing,
            "signal": _signal_dict(latest_signal, latest_decision),
            "decision_journal": [
                _decision_dict(d) for d in await decision_repo.get_recent_by_symbol(symbol, 8)
            ],
            "last_cycle_decisions": _last_cycle_decisions(manager),
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
        latest_signal = await signal_repo.get_latest(symbol)
        open_pos = await PositionRepository(session).get_by_symbol(symbol)

        trade_plan = None
        trade_levels: list[dict] = []
        level_specs: list[tuple[str, float | None, str, str]] = []

        if open_pos:
            trade_plan = {
                "action": open_pos.side.upper(),
                "entry": open_pos.entry_price,
                "stop_loss": open_pos.stop_loss,
                "take_profit": open_pos.take_profit,
                "source": "open_position",
                "reason": (open_pos.entry_explanation or "")[:200],
                "explanation": open_pos.entry_explanation,
            }
            level_specs = [
                ("Entry", open_pos.entry_price, "#2563eb", "solid"),
                ("Stop Loss", open_pos.stop_loss, "#dc2626", "dashed"),
                ("Take Profit", open_pos.take_profit, "#16a34a", "dashed"),
            ]
        elif latest_signal and latest_signal.action in ("BUY", "SELL"):
            trade_plan = {
                "action": latest_signal.action,
                "entry": latest_signal.entry_price,
                "stop_loss": latest_signal.stop_loss,
                "take_profit": latest_signal.take_profit,
                "confidence": latest_signal.confidence,
                "reason": latest_signal.reason,
                "explanation": latest_decision.explanation if latest_decision else latest_signal.reason,
                "regime": latest_decision.regime if latest_decision else None,
                "source": "signal",
            }
            level_specs = [
                ("Entry", latest_signal.entry_price, "#2563eb", "solid"),
                ("Stop Loss", latest_signal.stop_loss, "#dc2626", "dashed"),
                ("Take Profit", latest_signal.take_profit, "#16a34a", "dashed"),
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

        last_price = float(series[-1]["close"]) if series else (
            float(candles[-1].close) if candles else 0.0
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timeframe_label": label_for_timeframe(timeframe),
            "tradingview_symbol": f"BYBIT:{symbol}",
            "candles": series,
            "candles_dropped": candles_dropped,
            "candle_source": candle_source,
            "last_price": last_price,
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
        counts = await svc.ingest_symbol_tf(symbol.upper(), timeframe)
        return {"ingested": counts, "source": "bybit", "mode": "single", "symbol": symbol, "timeframe": timeframe}
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
            }
        )
    return out

