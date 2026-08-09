"""Market session control (start / pause / close)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import MarketSessionStatus


class MarketSession(Base):
    __tablename__ = "market_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[MarketSessionStatus] = mapped_column(
        Enum(MarketSessionStatus, name="market_session_status", native_enum=False),
        default=MarketSessionStatus.CREATED,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
