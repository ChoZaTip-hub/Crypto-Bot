"""Dashboard aggregate API for the web UI."""

from fastapi import APIRouter, Query

from app.api.deps import BotManagerDep, SessionDep, SettingsDep
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.candle_repo import CandleRepository
from app.db.repositories.news_repo import NewsRepository
from app.db.repositories.order_repo import OrderRepository
from app.db.repositories.position_repo import PositionRepository
from app.db.repositories.risk_repo import RiskRepository
from app.db.repositories.signal_repo import SignalRepository
from app.exchanges.bybit_client import BybitClient
from app.services.audit_service import AuditService
from app.services.indicator_service import IndicatorService
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def dashboard_overview(
    session: SessionDep,
    settings: SettingsDep,
    manager: BotManagerDep,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("5"),
) -> dict:
    symbol = symbol.upper()
    signal_repo = SignalRepository(session)
    news_repo = NewsRepository(session)
    risk_repo = RiskRepository(session)
    position_repo = PositionRepository(session)
    order_repo = OrderRepository(session)
    audit_repo = AuditRepository(session)
    candle_repo = CandleRepository(session)

    latest_signal = await signal_repo.get_latest(symbol)
    candles = await candle_repo.get_by_symbol_and_timeframe(symbol, timeframe, limit=120)
    indicators = await IndicatorService(session, AuditService(session)).compute_for_symbol(
        symbol, timeframe
    )

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
            "kill_switch": settings.kill_switch,
        },
        "symbol": symbol,
        "timeframe": timeframe,
        "last_price": float(candles[-1].close) if candles else 0,
        "indicators": {
            k: float(v) for k, v in indicators.items() if isinstance(v, (int, float))
        },
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


@router.get("/chart")
async def chart_data(
    session: SessionDep,
    settings: SettingsDep,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("5"),
    limit: int = Query(150, le=500),
) -> dict:
    symbol = symbol.upper()
    candle_repo = CandleRepository(session)
    signal_repo = SignalRepository(session)
    candles = await candle_repo.get_by_symbol_and_timeframe(symbol, timeframe, limit)
    indicators = await IndicatorService(session, AuditService(session)).compute_for_symbol(
        symbol, timeframe
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
        "candles": series,
        "overlays": overlays,
        "rsi": indicators.get("rsi"),
        "macd": indicators.get("macd"),
        "adx": indicators.get("adx"),
        "trade_plan": trade_plan,
        "market_source": "bybit" if settings.use_bybit_market_data else "mock",
    }


@router.post("/refresh-market")
async def refresh_market(session: SessionDep, settings: SettingsDep) -> dict:
    """Pull latest candles from Bybit into DB."""
    bybit = BybitClient(settings)
    audit = AuditService(session)
    repo = CandleRepository(session)
    svc = MarketDataService(bybit, repo, audit, settings)
    counts = await svc.ingest_all()
    return {"ingested": counts, "source": "bybit"}


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
