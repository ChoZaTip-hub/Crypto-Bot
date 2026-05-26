"""Circuit breaker on drawdown."""

from app.core.config import Settings


class CircuitBreaker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._triggered = False

    @property
    def is_triggered(self) -> bool:
        return self._triggered

    def check(self, drawdown_pct: float) -> bool:
        if drawdown_pct >= self._settings.circuit_breaker_drawdown:
            self._triggered = True
            return True
        return False

    def reset(self) -> None:
        self._triggered = False
