"""Indicator repository."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.indicator import IndicatorValue


class IndicatorRepository(BaseRepository[IndicatorValue]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, IndicatorValue)

    async def save_values(self, values: list[dict]) -> None:
        """Insert or update indicator rows (same candle bar may be recomputed each cycle)."""
        await self.bulk_upsert(values)

    async def bulk_upsert(self, values: list[dict]) -> None:
        if not values:
            return
        bind = self._session.get_bind()
        dialect = bind.dialect.name if bind is not None else "postgresql"

        if dialect == "postgresql":
            stmt = pg_insert(IndicatorValue).values(values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_indicator",
                set_={
                    "value": stmt.excluded.value,
                    "meta_json": stmt.excluded.meta_json,
                },
            )
            await self._session.execute(stmt)
        else:
            for row in values:
                stmt = select(IndicatorValue).where(
                    IndicatorValue.symbol == row["symbol"],
                    IndicatorValue.timeframe == row["timeframe"],
                    IndicatorValue.name == row["name"],
                    IndicatorValue.open_time == row["open_time"],
                )
                result = await self._session.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    existing.value = row["value"]
                    if "meta_json" in row:
                        existing.meta_json = row.get("meta_json")
                else:
                    self._session.add(IndicatorValue(**row))
        await self._session.flush()

    async def get_latest(self, symbol: str, timeframe: str, name: str) -> IndicatorValue | None:
        stmt = (
            select(IndicatorValue)
            .where(
                IndicatorValue.symbol == symbol,
                IndicatorValue.timeframe == timeframe,
                IndicatorValue.name == name,
            )
            .order_by(IndicatorValue.open_time.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_symbol(
        self, symbol: str, timeframe: str, name: str, limit: int = 100
    ) -> list[IndicatorValue]:
        stmt = (
            select(IndicatorValue)
            .where(
                IndicatorValue.symbol == symbol,
                IndicatorValue.timeframe == timeframe,
                IndicatorValue.name == name,
            )
            .order_by(IndicatorValue.open_time.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
