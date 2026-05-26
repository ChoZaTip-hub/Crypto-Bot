"""Parameter sweep optimizer (MVP-lite)."""

from typing import Any


class ParameterOptimizer:
    def sweep(self, param_grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
        keys = list(param_grid.keys())
        if not keys:
            return [{}]
        results: list[dict[str, Any]] = []

        def _recurse(idx: int, current: dict[str, Any]) -> None:
            if idx == len(keys):
                results.append(dict(current))
                return
            key = keys[idx]
            for val in param_grid[key]:
                current[key] = val
                _recurse(idx + 1, current)

        _recurse(0, {})
        return results
