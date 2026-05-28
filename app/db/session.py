"""Async database session management."""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


def _configure_sqlite(engine: AsyncEngine) -> None:
    """WAL mode allows concurrent reads while bot + background workers write."""

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA wal_autocheckpoint=1000")
        cursor.close()


class DatabaseSessionManager:
    def __init__(self, db_url: str, echo: bool = False) -> None:
        self._db_url = db_url
        self._echo = echo
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._is_sqlite = db_url.startswith("sqlite")

    def init_engine(self) -> None:
        kwargs: dict = {"echo": self._echo}
        if self._is_sqlite:
            kwargs["connect_args"] = {"timeout": 60}
            kwargs["poolclass"] = NullPool
        else:
            kwargs["pool_pre_ping"] = True

        self._engine = create_async_engine(self._db_url, **kwargs)
        if self._is_sqlite:
            _configure_sqlite(self._engine)

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Database engine not initialized")
        return self._engine

    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("Session factory not initialized")
        return self._session_factory

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        factory = self.session_factory()
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
