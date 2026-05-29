"""Portfolio tracking service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories.portfolio_repo import PortfolioRepository
from app.db.repositories.position_repo import PositionRepository
from app.models.fill import Fill
from app.models.order import TradeOrder
from app.risk.drawdown import DrawdownTracker


class PortfolioService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        account_id: int = 1,
    ) -> None:
        self._portfolio_repo = PortfolioRepository(session)
        self._position_repo = PositionRepository(session)
        self._session = session
        self._settings = settings
        self._account_id = account_id
        self._drawdown = DrawdownTracker()
        self._daily_pnl_pct = 0.0

    async def _initial_cash(self) -> float:
        from app.db.repositories.exchange_account_repo import ExchangeAccountRepository

        acc = await ExchangeAccountRepository(self._session).get_by_id(self._account_id)
        if acc and acc.paper_initial_balance:
            return float(acc.paper_initial_balance)
        return float(self._settings.paper_initial_balance)

    async def _cash_from_fills(self) -> float:
        """Paper/live cash = initial + sell proceeds - buy costs (per account)."""
        stmt = (
            select(Fill.side, Fill.qty, Fill.price)
            .join(TradeOrder, TradeOrder.order_id == Fill.order_id)
            .where(
                TradeOrder.account_id == self._account_id,
                TradeOrder.status == "filled",
            )
        )
        result = await self._session.execute(stmt)
        cash = await self._initial_cash()
        for side, qty, price in result.all():
            notional = float(qty) * float(price)
            side_u = str(side).upper()
            if side_u in ("BUY", "B"):
                cash -= notional
            else:
                cash += notional
        return cash

    async def _peak_equity(self) -> float:
        history = await self._portfolio_repo.get_history(limit=500)
        if not history:
            return 0.0
        return max(float(h.equity) for h in history)

    async def snapshot(self) -> dict:
        positions = await self._position_repo.get_open_positions(self._account_id)
        cash = await self._cash_from_fills()
        position_value = sum(
            float(p.current_price or p.entry_price or 0) * float(p.qty or 0)
            for p in positions
        )
        unrealized = sum(float(p.unrealized_pnl or 0) for p in positions)
        equity = cash + position_value
        peak = max(await self._peak_equity(), equity)
        dd = self._drawdown.update(equity, peak=peak if peak > 0 else None)

        prev = await self._portfolio_repo.get_latest()
        if prev and prev.equity and prev.equity > 0:
            self._daily_pnl_pct = (equity - float(prev.equity)) / float(prev.equity)

        snap = await self._portfolio_repo.save_snapshot(
            {
                "equity": equity,
                "cash_balance": cash,
                "unrealized_pnl": unrealized,
                "open_positions_count": len(positions),
                "daily_pnl": self._daily_pnl_pct * equity,
                "drawdown_pct": dd,
            }
        )
        return {
            "equity": snap.equity,
            "cash_balance": snap.cash_balance,
            "unrealized_pnl": snap.unrealized_pnl,
            "open_positions_count": snap.open_positions_count,
            "drawdown_pct": snap.drawdown_pct,
        }

    @property
    def daily_pnl_pct(self) -> float:
        return self._daily_pnl_pct
