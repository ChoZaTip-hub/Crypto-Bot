"""Order and fill endpoints."""

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.db.repositories.fill_repo import FillRepository
from app.db.repositories.order_repo import OrderRepository
from app.schemas.order import FillRead, OrderRead

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderRead])
async def list_orders(session: SessionDep, limit: int = Query(100)) -> list:
    return await OrderRepository(session).get_recent(limit)


@router.get("/open", response_model=list[OrderRead])
async def open_orders(session: SessionDep, symbol: str | None = None) -> list:
    return await OrderRepository(session).get_open_orders(symbol)


@router.get("/fills", response_model=list[FillRead])
async def list_fills(session: SessionDep, order_id: str | None = None) -> list:
    repo = FillRepository(session)
    if order_id:
        return await repo.get_by_order_id(order_id)
    return await repo.get_all(limit=100)
