"""Lightweight SQLite patches when Alembic migrations were not applied."""

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger

logger = get_logger(__name__)

# (table, column, sql type)
_SQLITE_COLUMN_PATCHES: tuple[tuple[str, str, str], ...] = (
    ("positions", "entry_explanation", "TEXT"),
    ("positions", "exit_explanation", "TEXT"),
    ("positions", "account_id", "INTEGER DEFAULT 1"),
    ("orders", "account_id", "INTEGER DEFAULT 1"),
)


async def patch_sqlite_schema(engine: AsyncEngine) -> None:
    """Add missing columns to existing SQLite tables (create_all does not ALTER)."""
    if not str(engine.url).startswith("sqlite"):
        return

    async with engine.begin() as conn:

        def _apply(sync_conn) -> None:
            insp = inspect(sync_conn)
            for table, column, col_type in _SQLITE_COLUMN_PATCHES:
                if table not in insp.get_table_names():
                    continue
                existing = {c["name"] for c in insp.get_columns(table)}
                if column in existing:
                    continue
                sync_conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                )
                logger.info("sqlite_column_added", table=table, column=column)

        await conn.run_sync(_apply)
