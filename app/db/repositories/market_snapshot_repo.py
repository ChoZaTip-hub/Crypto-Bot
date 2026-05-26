"""Market snapshot repository."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.market_snapshot import MarketSnapshot


class MarketSnapshotRepository(BaseRepository[MarketSnapshot]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MarketSnapshot)

    async def upsert_snapshot(
        self,
        symbol: str,
        timeframe: str,
        open_time: int,
        close: float,
        regime: str,
        indicators: dict,
    ) -> MarketSnapshot:
        stmt = select(MarketSnapshot).where(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.timeframe == timeframe,
            MarketSnapshot.open_time == open_time,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        payload = json.dumps(indicators)
        if existing:
            existing.close = close
            existing.regime = regime
            existing.indicators_json = payload
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        return await self.create(
            MarketSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                open_time=open_time,
                close=close,
                regime=regime,
                indicators_json=payload,
            )
        )

    async def get_latest(
        self, symbol: str, timeframe: str, before_open_time: int | None = None
    ) -> MarketSnapshot | None:
        stmt = select(MarketSnapshot).where(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.timeframe == timeframe,
        )
        if before_open_time is not None:
            stmt = stmt.where(MarketSnapshot.open_time < before_open_time)
        stmt = stmt.order_by(MarketSnapshot.open_time.desc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recent(self, symbol: str, timeframe: str, limit: int = 50) -> list[MarketSnapshot]:
        stmt = (
            select(MarketSnapshot)
            .where(MarketSnapshot.symbol == symbol, MarketSnapshot.timeframe == timeframe)
            .order_by(MarketSnapshot.open_time.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows
