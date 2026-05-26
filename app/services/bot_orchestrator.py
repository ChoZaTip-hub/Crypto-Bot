"""Main bot pipeline coordinator."""

import asyncio
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditEventType, SignalAction
from app.core.logging import get_logger
from app.exchanges.bybit_client import BybitClient
from app.exchanges.mock_exchange import MockExchange
from app.services.audit_service import AuditService
from app.services.execution_service import ExecutionService
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService
from app.services.portfolio_service import PortfolioService
from app.services.risk_service import RiskService
from app.services.sentiment_service import SentimentService
from app.services.strategy_service import StrategyService

logger = get_logger(__name__)


class BotOrchestrator:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._audit = AuditService(session)
        self._paper = MockExchange()
        self._bybit = BybitClient(settings)
        self._market_exchange = (
            self._bybit if settings.use_bybit_market_data else self._paper
        )

        from app.db.repositories.candle_repo import CandleRepository

        candle_repo = CandleRepository(session)
        self._market = MarketDataService(
            self._market_exchange, candle_repo, self._audit, settings
        )
        self._strategy = StrategyService(session, self._audit, settings.timeframes)
        self._risk = RiskService(session, settings, self._audit, self._market)
        self._execution = ExecutionService(
            session, self._bybit, self._paper, settings, self._audit
        )
        self._portfolio = PortfolioService(session, settings)
        self._news = NewsService(session, self._audit, settings)
        self._sentiment = SentimentService(session, self._audit)
        self._paper_connected = False

    @property
    def is_running(self) -> bool:
        return False  # use BotManager for running state

    async def _ensure_paper(self) -> None:
        if not self._paper_connected:
            await self._paper.connect()
            self._paper_connected = True

    async def run_pipeline(self) -> dict[str, Any]:
        """Full cycle: market (Bybit) → news → sentiment → signals → risk → paper execution."""
        await self._ensure_paper()
        market_counts = await self._market.ingest_all()
        news_counts = await self._news.ingest_all()
        await self._sentiment.score_recent_news(self._settings.symbol_whitelist)
        portfolio = await self._portfolio.snapshot()
        results: list[dict[str, Any]] = []

        for symbol in self._settings.symbol_whitelist:
            signal = await self._strategy.generate_signal(symbol)
            sentiment = await self._sentiment.get_latest(symbol)
            major_block = bool(sentiment and sentiment.high_impact)
            risk = await self._risk.evaluate(
                signal,
                equity=portfolio["equity"],
                daily_pnl_pct=self._portfolio.daily_pnl_pct,
                drawdown_pct=portfolio["drawdown_pct"],
                major_news_block=major_block,
            )
            order = None
            if signal.action != SignalAction.HOLD:
                order = await self._execution.execute(signal, risk)
            results.append(
                {
                    "symbol": symbol,
                    "action": signal.action.value,
                    "confidence": signal.confidence,
                    "reason": signal.reason,
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "risk_allowed": risk.allowed,
                    "risk_blocks": risk.blocks,
                    "order": order,
                }
            )

        return {
            "market_ingested": market_counts,
            "news_ingested": news_counts,
            "portfolio": portfolio,
            "decisions": results,
            "market_source": "bybit" if self._settings.use_bybit_market_data else "mock",
        }

    async def run_once(self) -> dict[str, Any]:
        return await self.run_pipeline()
