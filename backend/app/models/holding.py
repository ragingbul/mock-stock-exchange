"""Per-trader stock holdings with average cost basis."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.trader import Trader


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("trader_id", "stock_id", name="uq_holdings_trader_stock"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trader_id: Mapped[int] = mapped_column(
        ForeignKey("traders.id", ondelete="CASCADE"), index=True
    )
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trader: Mapped[Trader] = relationship("Trader", back_populates="holdings")
    stock: Mapped[Stock] = relationship("Stock", back_populates="holdings")
