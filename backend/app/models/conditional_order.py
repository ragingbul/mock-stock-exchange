"""Conditional orders: stop-loss and take-profit."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConditionalType(str, Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class ConditionalStatus(str, Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ConditionalOrder(Base):
    __tablename__ = "conditional_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trader_id: Mapped[int] = mapped_column(ForeignKey("traders.id"), index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), index=True)
    condition_type: Mapped[ConditionalType] = mapped_column(
        SAEnum(ConditionalType, name="conditional_type", native_enum=False)
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[ConditionalStatus] = mapped_column(
        SAEnum(ConditionalStatus, name="conditional_status", native_enum=False),
        default=ConditionalStatus.ACTIVE,
        index=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    linked_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
