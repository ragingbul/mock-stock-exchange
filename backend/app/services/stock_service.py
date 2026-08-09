"""Stock creation and lookup."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Stock
from app.schemas import StockCreate


class StockServiceError(Exception):
    """Domain error for stock operations."""


def create_stock(db: Session, payload: StockCreate) -> Stock:
    settings = get_settings()
    ticker = payload.ticker.strip().upper()
    if db.scalar(select(Stock).where(Stock.ticker == ticker)):
        raise StockServiceError(f"ticker already exists: {ticker}")

    tick_size = payload.tick_size
    if tick_size is None:
        tick_size = Decimal(str(settings.default_tick_size))

    stock = Stock(
        ticker=ticker,
        company_name=payload.company_name,
        sector=payload.sector,
        starting_price=payload.starting_price,
        last_traded_price=payload.starting_price,
        previous_close=payload.starting_price,
        shares_outstanding=payload.shares_outstanding,
        fair_value=payload.fair_value,
        volatility_class=payload.volatility_class,
        liquidity_class=payload.liquidity_class,
        fundamental_profile=payload.fundamental_profile,
        tick_size=tick_size,
        description=payload.description,
    )
    db.add(stock)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise StockServiceError("could not create stock") from exc
    db.refresh(stock)
    return stock


def get_stock(db: Session, stock_id: int) -> Stock | None:
    return db.get(Stock, stock_id)


def get_stock_by_ticker(db: Session, ticker: str) -> Stock | None:
    return db.scalar(select(Stock).where(Stock.ticker == ticker.strip().upper()))


def list_stocks(db: Session) -> list[Stock]:
    return list(db.scalars(select(Stock).order_by(Stock.ticker)).all())
