"""Portfolio and leaderboard snapshot tables."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trader_id: Mapped[int] = mapped_column(
        ForeignKey("traders.id", ondelete="CASCADE"), index=True
    )
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    portfolio_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class LeaderboardSnapshot(Base):
    __tablename__ = "leaderboard_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trader_id: Mapped[int] = mapped_column(
        ForeignKey("traders.id", ondelete="CASCADE"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    portfolio_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    return_pct: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"))
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    win_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    turnover: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(64), default="live")
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
