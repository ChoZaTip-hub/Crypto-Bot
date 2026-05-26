"""Render candle chart PNG for vision models (optional matplotlib)."""

from __future__ import annotations

import base64
import io
from typing import Sequence


def render_candles_png(
    closes: Sequence[float],
    *,
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
    title: str = "",
) -> bytes | None:
    if len(closes) < 10:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    fig, ax = plt.subplots(figsize=(8, 3), dpi=100)
    x = range(len(closes))
    ax.plot(x, list(closes), color="#3b82f6", linewidth=1.2, label="close")
    if highs and lows and len(highs) == len(closes):
        ax.fill_between(x, list(lows), list(highs), alpha=0.15, color="#94a3b8")
    ax.set_title(title or "Chart", fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="#0b0f14")
    plt.close(fig)
    return buf.getvalue()


def png_to_data_url(png: bytes) -> str:
    b64 = base64.standard_b64encode(png).decode("ascii")
    return f"data:image/png;base64,{b64}"
