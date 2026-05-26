"""Base indicator interface."""

from abc import ABC, abstractmethod


class BaseIndicator(ABC):
    name: str = "base"

    @abstractmethod
    def calculate(self, closes: list[float], **kwargs) -> float | dict[str, float]:
        ...
