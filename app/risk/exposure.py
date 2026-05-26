"""Exposure calculation."""

from app.models.position import Position


class ExposureCalculator:
    def symbol_exposure(self, positions: list[Position], symbol: str, equity: float) -> float:
        for p in positions:
            if p.symbol == symbol and p.is_open:
                notional = (p.current_price or p.entry_price) * p.qty
                return notional / equity if equity > 0 else 0.0
        return 0.0

    def total_open_positions(self, positions: list[Position]) -> int:
        return sum(1 for p in positions if p.is_open)
