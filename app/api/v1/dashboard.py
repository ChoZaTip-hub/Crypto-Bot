"""Dashboard aggregate API for the web UI."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import BackgroundManagerDep, BotManagerDep, SessionDep, SettingsDep
from app.core.logging import get_logger
from app.core.timeframes import BYBIT_TIMEFRAME_LABELS, label_for_timeframe
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.candle_repo import CandleRepository
from app.db.repositories.news_repo import NewsRepository
from app.db.repositories.order_repo import OrderRepository
from app.db.repositories.position_repo import PositionRepository
from app.db.repositories.risk_repo import RiskRepository
from app.db.repositories.market_change_repo import MarketChangeRepository
from app.db.repositories.signal_repo import SignalRepository
from app.services.learning_service import LearningService
from app.exchanges.bybit_client import BybitClient
from app.exchanges.exchange_types import CandleData
from app.services.audit_service import AuditService
from app.services.indicator_service import IndicatorService
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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
) -> dict:
    try:
        symbol = symbol.upper()
        signal_repo = SignalRepository(session)
        news_repo = NewsRepository(session)
        risk_repo = RiskRepository(session)
        position_repo = PositionRepository(session)
        order_repo = OrderRepository(session)
        audit_repo = AuditRepository(session)
        change_repo = MarketChangeRepository(session)
        learning_svc = LearningService(session, AuditService(session))

        latest_signal = await signal_repo.get_latest(symbol)
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
        for tf in settings.timeframes:
            tf_candles, _ = await _load_candles(symbol, tf, 120, session, settings)
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
            "signal": _signal_dict(latest_signal),
            "news": [_news_dict(n) for n in await news_repo.get_recent(15)],
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
                    "unrealized_pnl": p.unrealized_pnl,
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
        candles, candle_source = await _load_candles(symbol, timeframe, limit, session, settings)
        ind_svc = IndicatorService(session, AuditService(session))
        indicators = (
            ind_svc.compute_from_ohlcv(
                [c.close for c in candles],
                [c.high for c in candles],
                [c.low for c in candles],
                [c.volume for c in candles],
            )
            if candles
            else {}
        )
        latest_signal = await signal_repo.get_latest(symbol)

        series = [
            {
                "time": c.open_time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]

        overlays: list[dict] = []
        for key, color in (
            ("ema", "#60a5fa"),
            ("sma", "#a78bfa"),
            ("bb_upper", "#f87171"),
            ("bb_lower", "#4ade80"),
            ("vwap", "#fbbf24"),
        ):
            val = indicators.get(key)
            if isinstance(val, (int, float)):
                overlays.append({"name": key.upper(), "value": float(val), "color": color})

        trade_plan = None
        if latest_signal and latest_signal.action in ("BUY", "SELL"):
            trade_plan = {
                "action": latest_signal.action,
                "entry": latest_signal.entry_price,
                "stop_loss": latest_signal.stop_loss,
                "take_profit": latest_signal.take_profit,
                "confidence": latest_signal.confidence,
                "reason": latest_signal.reason,
            }
            for label, val, color in (
                ("Entry", latest_signal.entry_price, "#3b82f6"),
                ("Stop", latest_signal.stop_loss, "#ef4444"),
                ("TP", latest_signal.take_profit, "#22c55e"),
            ):
                if val:
                    overlays.append({"name": label, "value": float(val), "color": color})

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timeframe_label": label_for_timeframe(timeframe),
            "candles": series,
            "candle_source": candle_source,
            "overlays": overlays,
            "rsi": indicators.get("rsi"),
            "macd": indicators.get("macd"),
            "adx": indicators.get("adx"),
            "trade_plan": trade_plan,
            "market_source": "bybit" if settings.use_bybit_market_data else "mock",
        }
    except Exception as exc:
        logger.exception("dashboard_chart_failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/refresh-market")
async def refresh_market(session: SessionDep, settings: SettingsDep) -> dict:
    """Pull latest candles from Bybit for ALL configured timeframes."""
    bybit = BybitClient(settings)
    audit = AuditService(session)
    repo = CandleRepository(session)
    svc = MarketDataService(bybit, repo, audit, settings)
    counts = await svc.ingest_all()
    return {"ingested": counts, "source": "bybit", "timeframes": settings.timeframes}


@router.post("/refresh-news")
async def refresh_news(session: SessionDep, settings: SettingsDep) -> dict:
    svc = NewsService(session, AuditService(session), settings)
    counts = await svc.ingest_all()
    return {"ingested_by_provider": counts}


def _signal_dict(signal) -> dict | None:
    if not signal:
        return None
    return {
        "action": signal.action,
        "confidence": signal.confidence,
        "reason": signal.reason,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "risk_reward_ratio": signal.risk_reward_ratio,
        "created_at": signal.created_at.isoformat() if signal.created_at else None,
    }


def _news_dict(item) -> dict:
    return {
        "id": item.id,
        "source": item.source,
        "title": item.title,
        "summary": (item.summary or "")[:300],
        "url": item.url,
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }
