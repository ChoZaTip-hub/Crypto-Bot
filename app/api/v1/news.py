"""News and sentiment endpoints."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, SettingsDep
from app.core.security import verify_admin_token
from app.schemas.news import NewsItemRead, SentimentRead
from app.services.news_service import NewsService
from app.services.audit_service import AuditService
from app.services.sentiment_service import SentimentService

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=list[NewsItemRead])
async def news_feed(
    session: SessionDep,
    settings: SettingsDep,
    limit: int = Query(50),
) -> list:
    return await NewsService(session, AuditService(session), settings).get_recent(limit)


@router.post("/ingest", dependencies=[Depends(verify_admin_token)])
async def ingest_news(session: SessionDep, settings: SettingsDep) -> dict:
    svc = NewsService(session, AuditService(session), settings)
    counts = await svc.ingest_all()
    return {"ingested_by_provider": counts, "total": sum(counts.values())}


@router.get("/sources")
async def list_news_sources(settings: SettingsDep) -> dict:
    return {
        "rss_feeds": settings.news_rss_urls,
        "bybit_announcements_enabled": settings.bybit_announcements_enabled,
        "crypto_news_api_enabled": bool(settings.crypto_news_api_key),
        "known_rss_labels": [
            "CoinDesk",
            "Cointelegraph",
            "CryptoSlate",
            "Decrypt",
            "The Defiant",
            "CryptoPotato",
            "CryptoNews",
        ],
    }


@router.get("/sentiment/{symbol}", response_model=SentimentRead | None)
async def get_sentiment(symbol: str, session: SessionDep) -> SentimentRead | None:
    return await SentimentService(session, AuditService(session)).get_latest(symbol.upper())
