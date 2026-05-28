"""Serialize SQLite writes (bot cycle, background monitor, dashboard ingest)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

_write_lock = asyncio.Lock()


@asynccontextmanager
async def sqlite_write_lock():
    async with _write_lock:
        yield
