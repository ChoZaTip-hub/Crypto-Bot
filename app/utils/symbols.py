"""Symbol parsing helpers for spot USDT pairs."""

from itertools import combinations


def base_asset(symbol: str) -> str:
    """BTCUSDT -> BTC, ETHUSDT -> ETH."""
    s = symbol.upper().replace("/", "")
    if s.endswith("USDT"):
        return s[:-4]
    if s.endswith("USD"):
        return s[:-3]
    return s


def usdt_symbol(base: str) -> str:
    return f"{base.upper()}USDT"


def all_base_assets(symbols: list[str]) -> list[str]:
    return sorted({base_asset(s) for s in symbols})


def all_ratio_pairs(symbols: list[str]) -> list[tuple[str, str]]:
    """Unordered base pairs (BTC, ETH), (BTC, SOL), ..."""
    bases = all_base_assets(symbols)
    return [(a, b) for a, b in combinations(bases, 2)]
