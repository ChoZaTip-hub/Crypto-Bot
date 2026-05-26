"""News provider unit tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.news.bybit_announcements import (
    BybitAnnouncementsProvider,
    parse_announcement_rows,
)
from app.news.crypto_news_api import CryptoNewsApiProvider
from app.news.types import NewsItemDraft


@pytest.mark.asyncio
async def test_bybit_announcements_via_pybit() -> None:
    settings = Settings(bybit_announcements_enabled=True, bybit_testnet=True)
    mock_rest = MagicMock()
    mock_rest.get_announcement = AsyncMock(
        return_value={
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "total": 735,
                "list": [
                    {
                        "title": "New Listing: Arbitrum (ARB)",
                        "description": "Bybit is excited to announce the listing of ARB",
                        "type": {"title": "New Listings", "key": "new_crypto"},
                        "tags": ["Spot", "Spot Listings"],
                        "url": "https://announcements.bybit.com/en-US/article/test",
                        "dateTimestamp": 1679045608000,
                        "startDateTimestamp": 1679045608000,
                        "endDateTimestamp": 1679045608000,
                    }
                ],
            },
        }
    )
    provider = BybitAnnouncementsProvider(settings, rest_client=mock_rest)
    items = await provider.fetch()

    mock_rest.get_announcement.assert_awaited_once_with(locale="en-US", limit=20)
    assert len(items) == 1
    assert items[0].source == "Bybit Announcements"
    assert items[0].category == "new_crypto"
    assert "Spot" in items[0].tags


def test_parse_announcement_rows_matches_api_shape() -> None:
    rows = [
        {
            "title": "Delisting XYZ",
            "description": "Will delist",
            "type": {"key": "delistings", "title": "Delistings"},
            "tags": [],
            "url": "https://announcements.bybit.com/x",
            "dateTimestamp": 1679045608000,
        }
    ]
    items = parse_announcement_rows(rows)
    assert items[0].title == "Delisting XYZ"
    assert items[0].category == "delistings"


@pytest.mark.asyncio
async def test_crypto_news_api_disabled_without_key() -> None:
    settings = Settings(crypto_news_api_key="")
    provider = CryptoNewsApiProvider(settings)
    assert not provider.enabled
    items = await provider.fetch()
    assert items == []


@pytest.mark.asyncio
async def test_crypto_news_api_parses_response() -> None:
    from unittest.mock import patch

    settings = Settings(crypto_news_api_key="test-key", symbol_whitelist=["BTCUSDT"])
    provider = CryptoNewsApiProvider(settings)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {
                "title": "Bitcoin rises",
                "news_url": "https://example.com/btc",
                "text": "BTC up today",
                "date": "2024-01-15T12:00:00Z",
                "source_name": "Example",
                "sentiment": "Positive",
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.get.return_value = mock_response
        client_cls.return_value = client

        items = await provider.fetch()

    assert len(items) == 1
    assert "Crypto News API" in items[0].source


def test_news_item_draft_db_dict_includes_metadata() -> None:
    draft = NewsItemDraft(
        external_id="abc",
        source="Bybit Announcements",
        title="Delisting XYZ",
        summary="Token removed",
        provider="bybit_announcements",
        category="delistings",
        tags=["Spot"],
    )
    d = draft.to_db_dict()
    assert "[tags:" in d["summary"]
    assert "[category: delistings]" in d["summary"]
