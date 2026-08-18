"""Trader and user creation / lookup."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Trader, TraderType, User, UserRole
from app.schemas import TraderCreate


class TraderServiceError(Exception):
    """Domain error for trader operations."""


def create_trader(db: Session, payload: TraderCreate) -> Trader:
    settings = get_settings()
    capital = payload.starting_capital
    if capital is None:
        capital = Decimal(str(settings.default_starting_capital))
    if capital <= 0:
        raise TraderServiceError("starting_capital must be positive")

    user: User | None = None
    if payload.username:
        username = payload.username.strip().lower()
        existing = db.scalar(select(User).where(User.username == username))
        if existing:
            raise TraderServiceError(f"username already exists: {username}")
        user = User(
            username=username,
            display_name=payload.name,
            role=UserRole.PARTICIPANT,
            password_hash=None,
        )
        db.add(user)
        db.flush()

    trader = Trader(
        name=payload.name,
        trader_type=payload.trader_type,
        starting_capital=capital,
        cash=capital,
        cash_blocked_ipo=Decimal("0.00"),
        realized_pnl=Decimal("0.00"),
        user_id=user.id if user else None,
    )
    db.add(trader)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TraderServiceError("could not create trader") from exc
    db.refresh(trader)
    return trader


def get_trader(db: Session, trader_id: int) -> Trader | None:
    return db.get(Trader, trader_id)


def list_traders(db: Session, *, trader_type: TraderType | None = None) -> list[Trader]:
    stmt = select(Trader).order_by(Trader.id)
    if trader_type is not None:
        stmt = stmt.where(Trader.trader_type == trader_type)
    return list(db.scalars(stmt).all())
