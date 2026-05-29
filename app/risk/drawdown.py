"""Drawdown tracking."""


class DrawdownTracker:
    def __init__(self) -> None:
        self._peak_equity: float = 0.0

    def update(self, equity: float, *, peak: float | None = None) -> float:
        if peak is not None and peak > self._peak_equity:
            self._peak_equity = peak
        if equity > self._peak_equity:
            self._peak_equity = equity
        if self._peak_equity <= 0:
            return 0.0
        return (self._peak_equity - equity) / self._peak_equity
