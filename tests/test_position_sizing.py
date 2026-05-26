"""Position sizing tests."""

from app.core.config import Settings
from app.risk.position_sizing import PositionSizer


def test_fixed_usdt_qty() -> None:
    sizer = PositionSizer(Settings(position_size_mode="fixed_usdt", order_usdt=500))
    qty = sizer.compute_qty(equity=10_000, entry_price=50_000, stop_loss=49_000)
    assert abs(qty - 0.01) < 1e-9


def test_risk_percent_qty() -> None:
    sizer = PositionSizer(
        Settings(position_size_mode="risk_percent", max_risk_per_trade=0.01)
    )
    qty = sizer.compute_qty(equity=10_000, entry_price=100, stop_loss=95)
    assert qty > 0
