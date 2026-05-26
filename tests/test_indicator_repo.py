"""Indicator repository upsert tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.repositories.indicator_repo import IndicatorRepository
from app.models.indicator import IndicatorValue
from app.db.base import Base


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess
    await engine.dispose()


@pytest.mark.asyncio
async def test_indicator_upsert_updates_same_bar(session: AsyncSession) -> None:
    repo = IndicatorRepository(session)
    row = {
        "symbol": "BTCUSDT",
        "timeframe": "5",
        "name": "close",
        "open_time": 1_700_000_000,
        "value": 100.0,
    }
    await repo.save_values([row])
    await session.commit()

    row["value"] = 101.5
    await repo.save_values([row])
    await session.commit()

    latest = await repo.get_latest("BTCUSDT", "5", "close")
    assert latest is not None
    assert latest.value == 101.5

    from sqlalchemy import select, func

    count = await session.scalar(select(func.count()).select_from(IndicatorValue))
    assert count == 1
