"""News events (pre-loaded, manually rated)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NewsEvent(Base):
    __tablename__ = "news_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    # Comma-separated tickers, e.g. "TECHNOVA,DATACORE"
    affected_tickers: Mapped[str] = mapped_column(String(512), default="")
    # Comma-separated sectors
    affected_sectors: Mapped[str] = mapped_column(String(256), default="")
    market_wide: Mapped[bool] = mapped_column(Boolean, default=False)
    direction: Mapped[int] = mapped_column(Integer, default=0)  # -1, 0, +1
    impact: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"))
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("1"))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=20)
    decay_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=Decimal("0.05"))
    fundamental_impact_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    is_released: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
