"""Trader accounts — cash and P&L live here; holdings are separate rows."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TraderType

if TYPE_CHECKING:
    from app.models.holding import Holding
    from app.models.user import User


class Trader(Base):
    __tablename__ = "traders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), index=True)
    trader_type: Mapped[TraderType] = mapped_column(
        Enum(TraderType, name="trader_type", native_enum=False),
        default=TraderType.HUMAN,
    )
    starting_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User | None] = relationship("User", back_populates="trader")
    holdings: Mapped[list[Holding]] = relationship(
        "Holding", back_populates="trader", cascade="all, delete-orphan"
    )
