"""FastAPI dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.services.background_manager import BackgroundManager
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
    mgr = getattr(request.app.state, "bot_manager", None)
    if mgr is None:
        raise HTTPException(
            status_code=503,
            detail="API не готов. Запустите сервер: uvicorn app.main:app --reload --port 8000",
        )
    return mgr


def get_background_manager(request: Request) -> BackgroundManager:
    mgr = getattr(request.app.state, "background_manager", None)
    if mgr is None:
        raise HTTPException(
            status_code=503,
            detail="Фоновые сервисы не запущены. Перезапустите uvicorn.",
        )
    return mgr


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
BotManagerDep = Annotated[BotManager, Depends(get_bot_manager)]
BackgroundManagerDep = Annotated[BackgroundManager, Depends(get_background_manager)]
