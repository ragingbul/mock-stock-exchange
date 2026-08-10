"""News engine with exponential impact decay. Never sets LTP."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import NewsEvent, Stock
from app.models.enums import Sector


def effective_impact(event: NewsEvent, *, now: datetime | None = None) -> Decimal:
    if not event.is_released or event.released_at is None:
        return Decimal("0")
    now = now or datetime.now(timezone.utc)
    released = event.released_at
    if released.tzinfo is None:
        released = released.replace(tzinfo=timezone.utc)
    elapsed_min = max((now - released).total_seconds() / 60.0, 0.0)
    # I(t) = I0 * e^(-λt) * direction * confidence
    i0 = float(event.impact) * float(event.confidence) * float(event.direction)
    lam = float(event.decay_rate)
    value = i0 * math.exp(-lam * elapsed_min)
    # Tail after headline window — still meaningful for multi-news events
    if elapsed_min > event.duration_minutes:
        value *= float(get_settings().news_decay_tail_factor)
    return Decimal(str(round(value, 6)))


def create_news(db: Session, **kwargs) -> NewsEvent:
    event = NewsEvent(**kwargs)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def release_news(db: Session, event_id: int, *, now: datetime | None = None) -> NewsEvent:
    event = db.get(NewsEvent, event_id)
    if event is None:
        raise ValueError("news not found")
    now = now or datetime.now(timezone.utc)
    event.is_released = True
    event.released_at = now

    # Optional fundamental fair-value adjustment (does NOT set LTP)
    if event.fundamental_impact_pct is not None:
        tickers = [t.strip().upper() for t in event.affected_tickers.split(",") if t.strip()]
        sectors = [s.strip().lower() for s in event.affected_sectors.split(",") if s.strip()]
        stocks = list(db.scalars(select(Stock)).all())
        settings = get_settings()
        pct = Decimal(event.fundamental_impact_pct) * Decimal(str(settings.news_fundamental_multiplier))
        factor = Decimal("1") + (pct / Decimal("100"))
        for stock in stocks:
            apply = event.market_wide
            if stock.ticker in tickers:
                apply = True
            if stock.sector.value in sectors:
                apply = True
            elif sectors:
                first = sectors[0]
                if first in Sector._value2member_map_ and stock.sector == Sector(first):
                    apply = True
            if apply:
                stock.fair_value = (stock.fair_value * factor).quantize(Decimal("0.0001"))

    db.commit()
    db.refresh(event)
    return event


def list_news(db: Session, *, released_only: bool = False) -> list[NewsEvent]:
    stmt = select(NewsEvent).order_by(NewsEvent.id.desc())
    if released_only:
        stmt = stmt.where(NewsEvent.is_released.is_(True))
    return list(db.scalars(stmt).all())


def news_pressure_for_ticker(db: Session, ticker: str, *, now: datetime | None = None) -> Decimal:
    """Normalized news pressure for a ticker (amplified for event volatility)."""
    settings = get_settings()
    events = list_news(db, released_only=True)
    total = Decimal("0")
    for event in events:
        tickers = [t.strip().upper() for t in event.affected_tickers.split(",") if t.strip()]
        if event.market_wide or ticker.upper() in tickers:
            total += effective_impact(event, now=now)
    total *= Decimal(str(settings.news_pressure_amplifier))
    cap = Decimal(str(settings.news_pressure_cap))
    if total > cap:
        return cap
    if total < -cap:
        return -cap
    return total
