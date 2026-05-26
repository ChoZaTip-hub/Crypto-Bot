"""Historical cross-asset ratio snapshots (e.g. BTC/ETH)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PairRatioSnapshot(Base):
    __tablename__ = "pair_ratio_snapshots"
    __table_args__ = (
        UniqueConstraint("base_asset", "quote_asset", "sampled_at", name="uq_pair_ratio_sample"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    base_asset: Mapped[str] = mapped_column(String(16), index=True)
    quote_asset: Mapped[str] = mapped_column(String(16), index=True)
    ratio: Mapped[float] = mapped_column(Float)
    base_price_usdt: Mapped[float] = mapped_column(Float)
    quote_price_usdt: Mapped[float] = mapped_column(Float)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(32), default="live")
