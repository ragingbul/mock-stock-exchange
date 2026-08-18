"""Stock creation and lookup."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models import Stock
from app.schemas import StockCreate
from app.services import sector_service


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

    sector_service.ensure_sectors(db)
    sector_id = payload.sector_id
    if sector_id is None:
        linked = sector_service.resolve_sector_for_enum(db, payload.sector)
        sector_id = linked.id if linked else None

    stock = Stock(
        ticker=ticker,
        company_name=payload.company_name,
        sector=payload.sector,
        sector_id=sector_id,
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
    return db.scalar(
        select(Stock)
        .where(Stock.id == stock_id)
        .options(joinedload(Stock.market_sector))
    )


def get_stock_by_ticker(db: Session, ticker: str) -> Stock | None:
    return db.scalar(
        select(Stock)
        .where(Stock.ticker == ticker.strip().upper())
        .options(joinedload(Stock.market_sector))
    )


def list_stocks(db: Session, *, sector_id: int | None = None) -> list[Stock]:
    stmt = select(Stock).options(joinedload(Stock.market_sector)).order_by(Stock.ticker)
    if sector_id is not None:
        stmt = stmt.where(Stock.sector_id == sector_id)
    return list(db.scalars(stmt).unique().all())
