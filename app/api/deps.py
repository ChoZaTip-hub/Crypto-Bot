"""FastAPI dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.services.bot_manager import BotManager


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    manager = request.app.state.db_manager
    factory = manager.session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_settings_dep() -> Settings:
    return get_settings()


def get_bot_manager(request: Request) -> BotManager:
    return request.app.state.bot_manager


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
BotManagerDep = Annotated[BotManager, Depends(get_bot_manager)]
