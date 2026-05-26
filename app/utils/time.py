"""Time utilities."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_ts() -> int:
    return int(utc_now().timestamp())


def ms_to_ts(ms: int) -> int:
    return ms // 1000
