"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.init_db import DatabaseInitializer
from app.db.sqlite_schema import patch_sqlite_schema
from app.db.session import DatabaseSessionManager
from app.services.background_manager import BackgroundManager
from app.services.bot_manager import BotManager

STATIC_DIR = Path(__file__).resolve().parent / "static" / "dashboard"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CHARTING_LIB_DIR = Path(__file__).resolve().parent.parent / "charting_library"
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_manager = DatabaseSessionManager(settings.database_url, echo=settings.debug)
    db_manager.init_engine()
    try:
        await DatabaseInitializer(db_manager.engine).create_all()
        await patch_sqlite_schema(db_manager.engine)
    except OSError as exc:
        logger.error("database_connection_failed", url=settings.database_url, error=str(exc))
        raise RuntimeError(
            "Cannot connect to database. "
            "For local dev use DATABASE_URL=sqlite+aiosqlite:///./data/trading_bot.db "
            "or start Postgres: docker compose -f docker/docker-compose.yml up -d postgres"
        ) from exc
    app.state.db_manager = db_manager
    async with db_manager.session_factory()() as session:
        from app.services.account_bootstrap_service import AccountBootstrapService

        await AccountBootstrapService(session, settings).ensure_default_account()
        await session.commit()
    app.state.bot_manager = BotManager(db_manager, settings)
    app.state.background_manager = BackgroundManager(db_manager, settings)
    if settings.background_services_enabled:
        await app.state.background_manager.start()
    if settings.bot_auto_start:
        await app.state.bot_manager.start()
    yield
    await app.state.bot_manager.stop()
    if settings.background_services_enabled:
        await app.state.background_manager.stop()
    await db_manager.close()


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    if STATIC_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="dashboard-assets")

        @app.get("/")
        async def dashboard_page() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    if CHARTING_LIB_DIR.is_dir():
        app.mount(
            "/charting_library",
            StaticFiles(directory=CHARTING_LIB_DIR),
            name="tv-charting-library",
        )
        logger.info("tradingview_charting_library_mounted", path=str(CHARTING_LIB_DIR))

    return app


app = create_app()
