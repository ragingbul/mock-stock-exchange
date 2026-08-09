"""AI agent registry (strategy config). Agents are traders with trader_type=ai."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AIAgent(Base):
    __tablename__ = "ai_agents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trader_id: Mapped[int] = mapped_column(
        ForeignKey("traders.id", ondelete="CASCADE"), unique=True, index=True
    )
    strategy: Mapped[str] = mapped_column(String(64), index=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    capital: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    max_position: Mapped[int] = mapped_column(Integer, default=10_000)
    aggressiveness: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.5"))
    risk_tolerance: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0.5"))
    trade_frequency_seconds: Mapped[int] = mapped_column(Integer, default=15)
    allowed_tickers: Mapped[str] = mapped_column(String(512), default="*")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
