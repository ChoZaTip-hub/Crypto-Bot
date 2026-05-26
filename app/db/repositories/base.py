"""Generic async repository base."""

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, id_: int | str) -> ModelT | None:
        return await self._session.get(self._model, id_)

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        stmt = select(self._model).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, obj: ModelT) -> ModelT:
        self._session.add(obj)
        await self._session.flush()
        await self._session.refresh(obj)
        return obj

    async def delete(self, db_obj: ModelT) -> None:
        await self._session.delete(db_obj)
        await self._session.flush()

    async def exists(self, **filters: Any) -> bool:
        stmt = select(func.count()).select_from(self._model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self._model, key) == value)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self._model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self._model, key) == value)
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)
