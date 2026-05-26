"""User-confirmed cross-asset swap proposals."""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RatioSwapProposal(Base):
    __tablename__ = "ratio_swap_proposals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    base_asset: Mapped[str] = mapped_column(String(16), index=True)
    quote_asset: Mapped[str] = mapped_column(String(16), index=True)
    direction: Mapped[str] = mapped_column(String(32))
    from_asset: Mapped[str] = mapped_column(String(16))
    to_asset: Mapped[str] = mapped_column(String(16))
    from_qty: Mapped[float] = mapped_column(Float)
    to_qty: Mapped[float] = mapped_column(Float)
    ratio_current: Mapped[float] = mapped_column(Float)
    ratio_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    ratio_min_hist: Mapped[float | None] = mapped_column(Float, nullable=True)
    ratio_max_hist: Mapped[float | None] = mapped_column(Float, nullable=True)
    ratio_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    explanation: Mapped[str] = mapped_column(Text)
    user_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
