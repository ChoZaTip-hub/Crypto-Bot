"""Paper multi-asset holdings for ratio rotation strategy."""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetHolding(Base):
    __tablename__ = "asset_holdings"
    __table_args__ = (UniqueConstraint("asset", "trading_mode", name="uq_asset_mode"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(16), index=True)
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    trading_mode: Mapped[str] = mapped_column(String(16), default="paper")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
