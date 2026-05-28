"""Bybit account credentials and copy-trading preferences."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExchangeAccount(Base):
    __tablename__ = "exchange_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(128), default="account")
    exchange: Mapped[str] = mapped_column(String(32), default="bybit")
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")
    api_secret_encrypted: Mapped[str] = mapped_column(Text, default="")
    trading_mode: Mapped[str] = mapped_column(String(8), default="paper")
    live_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    copy_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    order_usdt: Mapped[float] = mapped_column(Float, default=100.0)
    position_size_mode: Mapped[str] = mapped_column(String(32), default="fixed_usdt")
    max_open_positions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paper_initial_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
