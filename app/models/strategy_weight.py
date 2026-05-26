"""Adaptive weights per regime and sub-strategy (rule-based + stats)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StrategyWeight(Base):
    __tablename__ = "strategy_weights"
    __table_args__ = (
        UniqueConstraint("regime", "sub_strategy", name="uq_strategy_weight"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    regime: Mapped[str] = mapped_column(String(32), index=True)
    sub_strategy: Mapped[str] = mapped_column(String(64), index=True)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    total_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    ml_bias: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
