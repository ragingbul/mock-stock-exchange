"""Stock definitions. last_traded_price is updated only by executions (later phases)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    FundamentalProfile,
    LiquidityClass,
    Sector,
    VolatilityClass,
)

if TYPE_CHECKING:
    from app.models.holding import Holding
    from app.models.sector import MarketSector


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(128))
    # Legacy enum code (kept for news matching + existing APIs)
    sector: Mapped[Sector] = mapped_column(
        Enum(Sector, name="sector", native_enum=False)
    )
    # First-class sector relationship (Layer 1)
    sector_id: Mapped[int | None] = mapped_column(
        ForeignKey("sectors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    starting_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    last_traded_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    previous_close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    shares_outstanding: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fair_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volatility_class: Mapped[VolatilityClass] = mapped_column(
        Enum(VolatilityClass, name="volatility_class", native_enum=False)
    )
    liquidity_class: Mapped[LiquidityClass] = mapped_column(
        Enum(LiquidityClass, name="liquidity_class", native_enum=False)
    )
    fundamental_profile: Mapped[FundamentalProfile] = mapped_column(
        Enum(FundamentalProfile, name="fundamental_profile", native_enum=False)
    )
    tick_size: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    is_halted: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    liquidation_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    holdings: Mapped[list[Holding]] = relationship("Holding", back_populates="stock")
    market_sector: Mapped[MarketSector | None] = relationship(
        "MarketSector", back_populates="stocks"
    )
