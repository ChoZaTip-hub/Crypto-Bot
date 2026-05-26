"""Indicator value ORM model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IndicatorValue(Base):
    __tablename__ = "indicator_values"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "name", "open_time", name="uq_indicator"),
        Index("ix_indicator_symbol_tf", "symbol", "timeframe", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(64))
    open_time: Mapped[int] = mapped_column(BigInteger)
    value: Mapped[float] = mapped_column(Float)
    meta_json: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
