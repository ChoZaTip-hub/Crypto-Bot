"""Risk manager unit tests."""

from app.core.config import Settings
from app.core.constants import SignalAction
from app.risk.manager import MarketContext, PortfolioState, RiskManager
from app.strategies.base import StrategySignal


def _signal(action: SignalAction = SignalAction.BUY) -> StrategySignal:
    return StrategySignal(
        symbol="BTCUSDT",
        action=action,
        confidence=0.8,
        reason="test",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        correlation_id="test-corr",
    )


def test_blocks_kill_switch() -> None:
    settings = Settings(kill_switch=True, max_open_positions=5)
    rm = RiskManager(settings)
    assessment = rm.assess(
        _signal(),
        MarketContext("BTCUSDT", 0, 0.01, False),
        PortfolioState(10000, 0, 0, 0, 0),
    )
    assert not assessment.allowed
    assert "kill_switch_active" in assessment.blocks


def test_blocks_stale_data() -> None:
    settings = Settings(kill_switch=False)
    rm = RiskManager(settings)
    assessment = rm.assess(
        _signal(),
        MarketContext("BTCUSDT", 0, 0.01, True),
        PortfolioState(10000, 0, 0, 0, 0),
    )
    assert not assessment.allowed
    assert "data_stale" in assessment.blocks


def test_allows_valid_buy() -> None:
    settings = Settings(
        kill_switch=False,
        max_open_positions=5,
        max_daily_loss=0.5,
        max_atr_pct=1.0,
    )
    rm = RiskManager(settings)
    assessment = rm.assess(
        _signal(SignalAction.BUY),
        MarketContext("BTCUSDT", 9999999999, 0.01, False),
        PortfolioState(10000, 0, 0, 0, 0),
    )
    assert assessment.allowed
    assert assessment.suggested_qty > 0
