"""Initialize database tables (dev only)."""

import asyncio

from app.core.config import get_settings
from app.db.init_db import DatabaseInitializer
from app.db.session import DatabaseSessionManager
import app.models  # noqa: F401


async def main() -> None:
    settings = get_settings()
    manager = DatabaseSessionManager(settings.database_url)
    manager.init_engine()
    init = DatabaseInitializer(manager.engine)
    await init.create_all()
    ok = await init.ping()
    print(f"Database initialized. Ping: {ok}")
    await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
