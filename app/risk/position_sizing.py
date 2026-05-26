"""Position sizing based on risk per trade."""

from app.core.config import Settings
from app.utils.math import safe_div


class PositionSizer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def compute_qty(
        self,
        equity: float,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        if entry_price <= 0:
            return 0.0
        max_notional = equity * self._settings.max_exposure_per_symbol
        max_qty = safe_div(max_notional, entry_price)

        if self._settings.position_size_mode == "fixed_usdt":
            qty = safe_div(self._settings.order_usdt, entry_price)
            return min(qty, max_qty) if max_qty > 0 else qty

        risk_amount = equity * self._settings.max_risk_per_trade
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            return 0.0
        qty = safe_div(risk_amount, risk_per_unit)
        return min(qty, max_qty)
