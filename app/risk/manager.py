"""Risk manager — deterministic trade approval."""

from dataclasses import dataclass, field

from app.core.config import Settings
from app.core.constants import RiskLevel, SignalAction
from app.risk.circuit_breaker import CircuitBreaker
from app.risk.drawdown import DrawdownTracker
from app.risk.exposure import ExposureCalculator
from app.risk.position_sizing import PositionSizer
from app.strategies.base import StrategySignal


@dataclass
class MarketContext:
    symbol: str
    last_candle_ts: int
    atr_pct: float
    data_stale: bool


@dataclass
class PortfolioState:
    equity: float
    daily_pnl_pct: float
    drawdown_pct: float
    open_positions_count: int
    symbol_exposure_pct: float


@dataclass
class RiskAssessment:
    allowed: bool
    blocks: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    daily_loss_ok: bool = True
    data_fresh_ok: bool = True
    suggested_qty: float = 0.0
    suggested_usdt: float = 0.0
    atr_pct: float = 0.0


class RiskManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sizer = PositionSizer(settings)
        self._exposure = ExposureCalculator()
        self._drawdown = DrawdownTracker()
        self._circuit = CircuitBreaker(settings)

    def assess(
        self,
        signal: StrategySignal,
        market: MarketContext,
        portfolio: PortfolioState,
    ) -> RiskAssessment:
        blocks: list[str] = []
        risk_score = signal.risk_score

        if self._settings.kill_switch:
            blocks.append("kill_switch_active")
        if self._circuit.check(portfolio.drawdown_pct):
            blocks.append("circuit_breaker_drawdown")
        if market.data_stale:
            blocks.append("data_stale")
        if market.atr_pct > self._settings.max_atr_pct:
            blocks.append("volatility_too_high")
        if portfolio.daily_pnl_pct <= -self._settings.max_daily_loss:
            blocks.append("max_daily_loss_exceeded")
        if portfolio.open_positions_count >= self._settings.max_open_positions:
            if signal.action != SignalAction.SELL:
                blocks.append("max_open_positions")
        if portfolio.symbol_exposure_pct >= self._settings.max_exposure_per_symbol:
            if signal.action == SignalAction.BUY:
                blocks.append("max_exposure_per_symbol")
        if signal.action in (SignalAction.BUY, SignalAction.SELL):
            if self._settings.mandatory_stop_loss and signal.stop_loss is None:
                blocks.append("mandatory_stop_loss_missing")

        allowed = len(blocks) == 0 and signal.action != SignalAction.HOLD
        suggested_qty = 0.0
        if allowed and signal.entry_price and signal.stop_loss:
            suggested_qty = self._sizer.compute_qty(
                portfolio.equity, signal.entry_price, signal.stop_loss
            )
            if suggested_qty <= 0:
                blocks.append("position_size_zero")
                allowed = False

        suggested_usdt = 0.0
        if suggested_qty > 0 and signal.entry_price:
            suggested_usdt = suggested_qty * float(signal.entry_price)

        return RiskAssessment(
            allowed=allowed,
            blocks=blocks,
            risk_score=risk_score,
            daily_loss_ok=portfolio.daily_pnl_pct > -self._settings.max_daily_loss,
            data_fresh_ok=not market.data_stale,
            suggested_qty=suggested_qty,
            suggested_usdt=suggested_usdt,
            atr_pct=market.atr_pct,
        )
