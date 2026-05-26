"""Drawdown tracking."""

class DrawdownTracker:
    def __init__(self) -> None:
        self._peak_equity: float = 0.0

    def update(self, equity: float) -> float:
        if equity > self._peak_equity:
            self._peak_equity = equity
        if self._peak_equity <= 0:
            return 0.0
        return (self._peak_equity - equity) / self._peak_equity
