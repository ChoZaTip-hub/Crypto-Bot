"""Portfolio tracking service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories.portfolio_repo import PortfolioRepository
from app.db.repositories.position_repo import PositionRepository
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
        self._settings = settings
        self._account_id = account_id
        self._drawdown = DrawdownTracker()
        self._daily_pnl_pct = 0.0

    async def snapshot(self) -> dict:
        positions = await self._position_repo.get_open_positions(self._account_id)
        cash = self._settings.paper_initial_balance
        unrealized = sum(p.unrealized_pnl for p in positions)
        equity = cash + unrealized
        dd = self._drawdown.update(equity)
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
