"""Candle series helpers for charts and ingestion."""


def filter_price_outliers(
    series: list[dict],
    max_dev_pct: float = 5.0,
) -> tuple[list[dict], int]:
    """Drop bars whose range is far from the median close (bad DB / API rows)."""
    if len(series) < 8:
        return series, 0
    closes = [float(c["close"]) for c in series]
    med = sorted(closes)[len(closes) // 2]
    if med <= 0:
        return series, 0
    band = med * max_dev_pct / 100.0
    lo, hi = med - band, med + band
    kept: list[dict] = []
    removed = 0
    for c in series:
        if float(c["low"]) < lo or float(c["high"]) > hi:
            removed += 1
            continue
        kept.append(c)
    return kept, removed


def sanitize_ohlc_rows(rows: list[dict], max_dev_pct: float = 8.0) -> list[dict]:
    """Filter dict rows before DB upsert (open/high/low/close keys)."""
    if len(rows) < 3:
        return rows
    closes = [float(r["close"]) for r in rows]
    med = sorted(closes)[len(closes) // 2]
    if med <= 0:
        return rows
    band = med * max_dev_pct / 100.0
    lo, hi = med - band, med + band
    return [r for r in rows if float(r["low"]) >= lo and float(r["high"]) <= hi]
