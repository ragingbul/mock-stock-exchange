"""Persistent orders submitted through the order gateway."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.order_enums import OrderSide, OrderStatus, OrderType

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.trader import Trader


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trader_id: Mapped[int] = mapped_column(
        ForeignKey("traders.id", ondelete="CASCADE"), index=True
    )
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), index=True
    )
    side: Mapped[OrderSide] = mapped_column(
        Enum(OrderSide, name="order_side", native_enum=False)
    )
    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType, name="order_type", native_enum=False)
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Limit price; null for market orders
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", native_enum=False),
        default=OrderStatus.OPEN,
        index=True,
    )
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trader: Mapped[Trader] = relationship("Trader")
    stock: Mapped[Stock] = relationship("Stock")
