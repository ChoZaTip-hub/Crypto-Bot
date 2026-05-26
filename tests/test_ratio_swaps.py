"""Ratio pair and swap math tests."""

from app.utils.symbols import all_base_assets, all_ratio_pairs, base_asset


def test_base_asset_parsing() -> None:
    assert base_asset("BTCUSDT") == "BTC"
    assert base_asset("ETHUSDT") == "ETH"


def test_all_pairs_from_whitelist() -> None:
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    bases = all_base_assets(symbols)
    assert bases == ["BTC", "ETH", "SOL"]
    pairs = all_ratio_pairs(symbols)
    assert ("BTC", "ETH") in pairs
    assert len(pairs) == 3


def test_swap_math_btc_eth_example() -> None:
    """1 BTC at ratio 36 -> 36 ETH; at ratio 12 -> 3 BTC."""
    btc = 1.0
    ratio_high = 36.0
    eth = btc * ratio_high
    assert eth == 36.0
    ratio_low = 12.0
    btc_back = eth / ratio_low
    assert abs(btc_back - 3.0) < 1e-9
