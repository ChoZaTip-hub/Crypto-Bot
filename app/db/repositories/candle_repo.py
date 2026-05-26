"""Candle repository."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.candle import Candle


class CandleRepository(BaseRepository[Candle]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Candle)

    async def get_by_symbol_and_timeframe(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> list[Candle]:
        stmt = (
            select(Candle)
            .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
            .order_by(Candle.open_time.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def get_latest(self, symbol: str, timeframe: str) -> Candle | None:
        stmt = (
            select(Candle)
            .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
            .order_by(Candle.open_time.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def bulk_upsert(self, candles: list[dict]) -> None:
        if not candles:
            return
        bind = self._session.get_bind()
        dialect = bind.dialect.name if bind is not None else "postgresql"

        if dialect == "postgresql":
            stmt = pg_insert(Candle).values(candles)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_candle",
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "turnover": stmt.excluded.turnover,
                    "close_time": stmt.excluded.close_time,
                },
            )
            await self._session.execute(stmt)
        else:
            for row in candles:
                stmt = select(Candle).where(
                    Candle.symbol == row["symbol"],
                    Candle.timeframe == row["timeframe"],
                    Candle.open_time == row["open_time"],
                )
                result = await self._session.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    for key in ("open", "high", "low", "close", "volume", "turnover", "close_time"):
                        setattr(existing, key, row[key])
                else:
                    self._session.add(Candle(**row))
        await self._session.flush()

    async def get_range(
        self, symbol: str, timeframe: str, start_ts: int, end_ts: int
    ) -> list[Candle]:
        stmt = (
            select(Candle)
            .where(
                Candle.symbol == symbol,
                Candle.timeframe == timeframe,
                Candle.open_time >= start_ts,
                Candle.open_time <= end_ts,
            )
            .order_by(Candle.open_time.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
