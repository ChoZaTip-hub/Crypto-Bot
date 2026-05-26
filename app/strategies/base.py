"""Strategy base types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.constants import DEFAULT_STRATEGY_VERSION, SignalAction


@dataclass
class StrategyInputs:
    symbol: str
    timeframes: dict[str, dict[str, Any]]
    sentiment_score: float = 0.0
    sentiment_high_impact: bool = False
    regime: str = "unknown"


@dataclass
class StrategySignal:
    symbol: str
    action: SignalAction
    confidence: float
    reason: str
    risk_score: float = 0.0
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward_ratio: float | None = None
    correlation_id: str = ""
    timeframe_confirmations: list[str] = field(default_factory=list)
    strategy_name: str = "multi_timeframe"
    strategy_version: str = DEFAULT_STRATEGY_VERSION


class BaseStrategy(ABC):
    name: str = "base"
    version: str = DEFAULT_STRATEGY_VERSION

    @abstractmethod
    async def decide(self, inputs: StrategyInputs) -> StrategySignal:
        ...
