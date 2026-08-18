"""IPO offerings and applications."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IPOStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    ALLOTTED = "allotted"
    LISTED = "listed"
    CANCELLED = "cancelled"


class IPOApplicationStatus(str, Enum):
    APPLIED = "applied"
    PARTIALLY_ALLOTTED = "partially_allotted"
    FULLY_ALLOTTED = "fully_allotted"
    NOT_ALLOTTED = "not_allotted"
    CANCELLED = "cancelled"


class IPO(Base):
    __tablename__ = "ipos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(128))
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id"), nullable=True)
    issue_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    lot_size: Mapped[int] = mapped_column(Integer, nullable=False)
    total_lots: Mapped[int] = mapped_column(Integer, nullable=False)
    winning_lots: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_lots_per_user: Mapped[int] = mapped_column(Integer, default=2)
    application_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    application_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    listing_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[IPOStatus] = mapped_column(
        SAEnum(IPOStatus, name="ipo_status", native_enum=False),
        default=IPOStatus.DRAFT,
        index=True,
    )
    stock_id: Mapped[int | None] = mapped_column(ForeignKey("stocks.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeline_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IPOApplication(Base):
    __tablename__ = "ipo_applications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ipo_id: Mapped[int] = mapped_column(ForeignKey("ipos.id"), index=True)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), index=True)
    requested_lots: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_lots: Mapped[int] = mapped_column(Integer, default=0)
    amount_blocked: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    amount_used: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    status: Mapped[IPOApplicationStatus] = mapped_column(
        SAEnum(IPOApplicationStatus, name="ipo_application_status", native_enum=False),
        default=IPOApplicationStatus.APPLIED,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
