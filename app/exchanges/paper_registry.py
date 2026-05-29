"""Per-account paper exchange instances (isolated balances)."""

from __future__ import annotations

from app.exchanges.mock_exchange import MockExchange

_registry: dict[int, MockExchange] = {}


def get_paper_exchange(account_id: int, *, initial_balance: float | None = None) -> MockExchange:
    if account_id not in _registry:
        _registry[account_id] = MockExchange(
            account_id=account_id,
            initial_balance=initial_balance,
        )
    return _registry[account_id]


def reset_paper_registry() -> None:
    _registry.clear()
