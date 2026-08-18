"""Fixed per-news per-stock target impacts (deterministic variation)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func

from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NewsStockImpact(Base):
    __tablename__ = "news_stock_impacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    news_event_id: Mapped[int] = mapped_column(
        ForeignKey("news_events.id", ondelete="CASCADE"), index=True
    )
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), index=True
    )
    sector_slug: Mapped[str] = mapped_column(String(64))
    sector_impact_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    variation_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    target_impact_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    reference_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    target_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
