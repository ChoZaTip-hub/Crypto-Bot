"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    backtests,
    bot,
    dashboard,
    health,
    learning,
    market,
    memory,
    orders,
    positions,
    ratio_swaps,
    risk,
    signals,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(ai.router)
api_router.include_router(dashboard.router)
api_router.include_router(bot.router)
api_router.include_router(memory.router)
api_router.include_router(learning.router)
api_router.include_router(market.router)
api_router.include_router(signals.router)
api_router.include_router(orders.router)
api_router.include_router(positions.router)
api_router.include_router(ratio_swaps.router)
api_router.include_router(risk.router)
api_router.include_router(backtests.router)
api_router.include_router(admin.router)
