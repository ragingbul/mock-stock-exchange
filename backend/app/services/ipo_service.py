"""IPO create / apply / allot / list — cash blocking via trader.cash_blocked_ipo."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Stock, Trader
from app.models.enums import (
    FundamentalProfile,
    LiquidityClass,
    Sector,
    VolatilityClass,
)
from app.models.ipo import IPO, IPOApplication, IPOApplicationStatus, IPOStatus
from app.schemas import HoldingAdjust, StockCreate
from app.services import portfolio_service, sector_service, stock_service
from app.services.liquidity_service import provision_two_sided_quotes


class IPOServiceError(Exception):
    pass


def create_ipo(db: Session, **kwargs) -> IPO:
    ticker = str(kwargs.get("ticker", "")).strip().upper()
    if not ticker:
        raise IPOServiceError("ticker required")
    if stock_service.get_stock_by_ticker(db, ticker):
        raise IPOServiceError(f"ticker already listed: {ticker}")
    existing = db.scalar(select(IPO).where(IPO.ticker == ticker, IPO.status != IPOStatus.CANCELLED))
    if existing and existing.status not in {IPOStatus.LISTED, IPOStatus.CANCELLED}:
        raise IPOServiceError(f"active IPO already exists for {ticker}")

    ipo = IPO(
        company_name=kwargs["company_name"],
        ticker=ticker,
        sector_id=kwargs.get("sector_id"),
        issue_price=Decimal(str(kwargs["issue_price"])),
        lot_size=int(kwargs["lot_size"]),
        total_lots=int(kwargs["total_lots"]),
        winning_lots=int(kwargs["winning_lots"]),
        maximum_lots_per_user=int(kwargs.get("maximum_lots_per_user") or 2),
        application_start=kwargs.get("application_start"),
        application_end=kwargs.get("application_end"),
        listing_time=kwargs.get("listing_time"),
        status=IPOStatus(kwargs.get("status") or IPOStatus.DRAFT),
        description=kwargs.get("description"),
    )
    if ipo.winning_lots > ipo.total_lots:
        raise IPOServiceError("winning_lots cannot exceed total_lots")
    db.add(ipo)
    db.commit()
    db.refresh(ipo)
    return ipo


def update_ipo(db: Session, ipo_id: int, **kwargs) -> IPO:
    ipo = db.get(IPO, ipo_id)
    if ipo is None:
        raise IPOServiceError("ipo not found")
    if ipo.status in {IPOStatus.ALLOTTED, IPOStatus.LISTED, IPOStatus.CANCELLED}:
        raise IPOServiceError("cannot edit IPO after allotment")
    for key, value in kwargs.items():
        if value is not None and hasattr(ipo, key):
            setattr(ipo, key, value)
    db.commit()
    db.refresh(ipo)
    return ipo


def open_ipo(db: Session, ipo_id: int) -> IPO:
    ipo = db.get(IPO, ipo_id)
    if ipo is None:
        raise IPOServiceError("ipo not found")
    ipo.status = IPOStatus.OPEN
    if ipo.application_start is None:
        ipo.application_start = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ipo)
    return ipo


def apply_ipo(db: Session, *, ipo_id: int, trader_id: int, requested_lots: int) -> IPOApplication:
    ipo = db.get(IPO, ipo_id)
    trader = db.get(Trader, trader_id)
    if ipo is None or trader is None:
        raise IPOServiceError("ipo or trader not found")
    if ipo.status != IPOStatus.OPEN:
        raise IPOServiceError("IPO is not open for applications")
    if requested_lots <= 0:
        raise IPOServiceError("requested_lots must be positive")
    if requested_lots > ipo.maximum_lots_per_user:
        raise IPOServiceError(f"max lots per user is {ipo.maximum_lots_per_user}")

    existing = db.scalar(
        select(IPOApplication).where(
            IPOApplication.ipo_id == ipo_id,
            IPOApplication.trader_id == trader_id,
            IPOApplication.status == IPOApplicationStatus.APPLIED,
        )
    )
    if existing:
        raise IPOServiceError("already applied for this IPO")

    amount = Decimal(ipo.issue_price) * ipo.lot_size * requested_lots
    if trader.cash < amount:
        raise IPOServiceError("insufficient available cash")

    trader.cash -= amount
    trader.cash_blocked_ipo = Decimal(trader.cash_blocked_ipo or 0) + amount

    app = IPOApplication(
        ipo_id=ipo_id,
        trader_id=trader_id,
        requested_lots=requested_lots,
        allocated_lots=0,
        amount_blocked=amount,
        amount_used=Decimal("0"),
        status=IPOApplicationStatus.APPLIED,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def close_applications(db: Session, ipo_id: int) -> IPO:
    ipo = db.get(IPO, ipo_id)
    if ipo is None:
        raise IPOServiceError("ipo not found")
    if ipo.status != IPOStatus.OPEN:
        raise IPOServiceError("IPO must be open to close applications")
    ipo.status = IPOStatus.CLOSED
    ipo.application_end = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ipo)
    return ipo


def allot_ipo(db: Session, ipo_id: int, *, seed: int | None = None) -> dict:
    ipo = db.get(IPO, ipo_id)
    if ipo is None:
        raise IPOServiceError("ipo not found")
    if ipo.status not in {IPOStatus.CLOSED, IPOStatus.OPEN}:
        raise IPOServiceError("IPO must be closed (or open) before allotment")
    if ipo.status == IPOStatus.OPEN:
        ipo.status = IPOStatus.CLOSED

    apps = list(
        db.scalars(
            select(IPOApplication).where(
                IPOApplication.ipo_id == ipo_id,
                IPOApplication.status == IPOApplicationStatus.APPLIED,
            )
        ).all()
    )
    # Expand to lot tokens for random draw
    tickets: list[tuple[IPOApplication, int]] = []
    for app in apps:
        for i in range(app.requested_lots):
            tickets.append((app, i))

    rng = random.Random(seed if seed is not None else get_settings().random_seed)
    rng.shuffle(tickets)

    remaining = ipo.winning_lots
    allocated: dict[int, int] = {app.id: 0 for app in apps}
    for app, _idx in tickets:
        if remaining <= 0:
            break
        if allocated[app.id] >= ipo.maximum_lots_per_user:
            continue
        allocated[app.id] += 1
        remaining -= 1

    results = []
    for app in apps:
        lots = allocated.get(app.id, 0)
        used = Decimal(ipo.issue_price) * ipo.lot_size * lots
        release = app.amount_blocked - used
        trader = db.get(Trader, app.trader_id)
        if trader is None:
            continue
        trader.cash_blocked_ipo = Decimal(trader.cash_blocked_ipo or 0) - app.amount_blocked
        if trader.cash_blocked_ipo < 0:
            trader.cash_blocked_ipo = Decimal("0")
        if release > 0:
            trader.cash += release
        app.allocated_lots = lots
        app.amount_used = used
        if lots == 0:
            app.status = IPOApplicationStatus.NOT_ALLOTTED
        elif lots >= app.requested_lots:
            app.status = IPOApplicationStatus.FULLY_ALLOTTED
        else:
            app.status = IPOApplicationStatus.PARTIALLY_ALLOTTED
        results.append(
            {
                "application_id": app.id,
                "trader_id": app.trader_id,
                "requested_lots": app.requested_lots,
                "allocated_lots": lots,
                "amount_used": str(used),
                "amount_released": str(release),
                "status": app.status.value,
            }
        )

    ipo.status = IPOStatus.ALLOTTED
    db.commit()
    return {"ipo_id": ipo.id, "allocations": results}


def list_ipo(db: Session, ipo_id: int) -> dict:
    """Create stock and credit allotted shares to winners."""
    ipo = db.get(IPO, ipo_id)
    if ipo is None:
        raise IPOServiceError("ipo not found")
    if ipo.status != IPOStatus.ALLOTTED:
        raise IPOServiceError("IPO must be allotted before listing")
    if stock_service.get_stock_by_ticker(db, ipo.ticker):
        raise IPOServiceError("stock already exists")

    sector_service.ensure_sectors(db)
    sector_enum = Sector.TECH
    if ipo.sector_id:
        sector = sector_service.get_sector(db, ipo.sector_id)
        if sector:
            from app.services.sector_service import SLUG_TO_ENUM

            sector_enum = SLUG_TO_ENUM.get(sector.slug, Sector.TECH)

    stock = stock_service.create_stock(
        db,
        StockCreate(
            ticker=ipo.ticker,
            company_name=ipo.company_name,
            sector=sector_enum,
            sector_id=ipo.sector_id,
            starting_price=ipo.issue_price,
            shares_outstanding=ipo.total_lots * ipo.lot_size * 100,
            fair_value=ipo.issue_price,
            volatility_class=VolatilityClass.MEDIUM,
            liquidity_class=LiquidityClass.MEDIUM,
            fundamental_profile=FundamentalProfile.GROWTH,
            description=ipo.description or f"Listed via IPO {ipo.ticker}",
        ),
    )

    apps = list(
        db.scalars(
            select(IPOApplication).where(
                IPOApplication.ipo_id == ipo_id,
                IPOApplication.allocated_lots > 0,
            )
        ).all()
    )
    for app in apps:
        shares = app.allocated_lots * ipo.lot_size
        portfolio_service.set_holding(
            db,
            app.trader_id,
            HoldingAdjust(stock_id=stock.id, quantity=shares, avg_cost=ipo.issue_price),
        )

    provision_two_sided_quotes(db, stock)
    ipo.stock_id = stock.id
    ipo.status = IPOStatus.LISTED
    ipo.listing_time = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ipo)
    return {"ipo_id": ipo.id, "stock_id": stock.id, "ticker": stock.ticker, "allottees": len(apps)}


def list_ipos(db: Session) -> list[IPO]:
    return list(db.scalars(select(IPO).order_by(IPO.id.desc())).all())


def list_applications(db: Session, *, ipo_id: int | None = None, trader_id: int | None = None) -> list[IPOApplication]:
    stmt = select(IPOApplication)
    if ipo_id is not None:
        stmt = stmt.where(IPOApplication.ipo_id == ipo_id)
    if trader_id is not None:
        stmt = stmt.where(IPOApplication.trader_id == trader_id)
    return list(db.scalars(stmt.order_by(IPOApplication.id.desc())).all())
