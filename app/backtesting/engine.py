"""Backtest engine."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.metrics import PerformanceMetrics
from app.backtesting.simulator import TradeSimulator
from app.core.config import get_settings
from app.db.repositories.backtest_repo import BacktestRepository
from app.db.repositories.candle_repo import CandleRepository
from app.services.indicator_service import IndicatorService
from app.services.audit_service import AuditService
from app.strategies.base import StrategyInputs
from app.strategies.multi_timeframe_strategy import MultiTimeframeStrategy
from app.utils.serialization import dumps_json


class BacktestEngine:
    def __init__(self, session: AsyncSession) -> None:
        self._candle_repo = CandleRepository(session)
        self._backtest_repo = BacktestRepository(session)
        self._audit = AuditService(session)
        self._indicator = IndicatorService(session, self._audit)
        self._strategy = MultiTimeframeStrategy()
        self._metrics = PerformanceMetrics()

    async def run(
        self,
        name: str,
        symbols: list[str],
        timeframes: list[str],
        start_ts: int,
        end_ts: int,
        strategy_version: str = "multi_tf_v1",
    ) -> int:
        settings = get_settings()
        simulator = TradeSimulator(
            initial_balance=settings.paper_initial_balance,
            slippage_bps=settings.paper_slippage_bps,
        )
        all_pnls: list[float] = []
        equity_curve = [simulator.balance]

        for symbol in symbols:
            tf_data: dict[str, dict] = {}
            primary_tf = timeframes[0] if timeframes else "5"
            candles = await self._candle_repo.get_range(symbol, primary_tf, start_ts, end_ts)
            if len(candles) < 30:
                continue
            for i in range(30, len(candles)):
                subset = candles[: i + 1]
                closes = [c.close for c in subset]
                tf_data[primary_tf] = {
                    "close": closes[-1],
                    "rsi": 50.0,
                    "adx": 20.0,
                    "atr": abs(closes[-1] - closes[-2]) if len(closes) > 1 else 0,
                    "ema": sum(closes[-20:]) / min(20, len(closes)),
                    "bb_lower": min(closes[-20:]),
                    "bb_upper": max(closes[-20:]),
                }
                inputs = StrategyInputs(symbol=symbol, timeframes=tf_data)
                signal = await self._strategy.decide(inputs)
                bar = subset[-1]
                simulator.process_bar(
                    symbol,
                    bar.open_time,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    signal.action.value,
                    signal.stop_loss,
                    signal.take_profit,
                )

        for t in simulator.trades:
            all_pnls.append(t.pnl)
            equity_curve.append(simulator.balance)

        result = await self._backtest_repo.save_result(
            {
                "name": name,
                "symbols": ",".join(symbols),
                "timeframes": ",".join(timeframes),
                "start_ts": start_ts,
                "end_ts": end_ts,
                "strategy_version": strategy_version,
                "total_trades": len(simulator.trades),
                "win_rate": self._metrics.win_rate(all_pnls),
                "max_drawdown": self._metrics.max_drawdown(equity_curve),
                "sharpe_ratio": self._metrics.sharpe_ratio(all_pnls),
                "profit_factor": self._metrics.profit_factor(all_pnls),
                "expectancy": self._metrics.expectancy(all_pnls),
                "total_pnl": sum(all_pnls),
                "params_json": dumps_json({}),
            }
        )
        await self._backtest_repo.save_trade_rows(
            result.id,
            [
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "qty": t.qty,
                    "pnl": t.pnl,
                    "entry_ts": t.entry_ts,
                    "exit_ts": t.exit_ts,
                }
                for t in simulator.trades
            ],
        )
        return result.id
