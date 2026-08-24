"""News engine with exponential impact decay. Never sets LTP."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models import NewsEvent, Stock
from app.models.enums import Sector
from app.services import sector_service
from app.services.news_impact_resolver import snapshot_baselines_on_release


def _stock_matches_sectors(stock: Stock, sectors: list[str]) -> bool:
    if not sectors:
        return False
    codes = {stock.sector.value}
    if stock.market_sector is not None:
        codes.add(stock.market_sector.slug)
        mapped = sector_service.ENUM_TO_SECTOR_SLUG.get(stock.sector.value)
        if mapped:
            codes.add(mapped)
    return any(s in codes for s in sectors)


def effective_impact(event: NewsEvent, *, now: datetime | None = None) -> Decimal:
    if not event.is_released or event.released_at is None:
        return Decimal("0")
    now = now or datetime.now(timezone.utc)
    released = event.released_at
    if released.tzinfo is None:
        released = released.replace(tzinfo=timezone.utc)
    elapsed_min = max((now - released).total_seconds() / 60.0, 0.0)
    i0 = float(event.impact) * float(event.confidence) * float(event.direction)
    lam = float(event.decay_rate)
    value = i0 * math.exp(-lam * elapsed_min)
    if elapsed_min > event.duration_minutes:
        value *= float(get_settings().news_decay_tail_factor)
    return Decimal(str(round(value, 6)))


def create_news(db: Session, **kwargs) -> NewsEvent:
    sector_impacts = kwargs.pop("sector_impacts", None)
    stock_impacts = kwargs.pop("stock_impacts", None)
    market_wide_impact_pct = kwargs.pop("market_wide_impact_pct", None)
    brief_points = kwargs.pop("brief_points", None)
    status = kwargs.pop("status", None)
    if sector_impacts is not None and not isinstance(sector_impacts, str):
        kwargs["sector_impacts_json"] = json.dumps(sector_impacts)
    if stock_impacts is not None and not isinstance(stock_impacts, str):
        kwargs["stock_impacts_json"] = json.dumps(stock_impacts)
    if brief_points is not None and not isinstance(brief_points, str):
        kwargs["brief_points_json"] = json.dumps(brief_points)
    if market_wide_impact_pct is not None:
        kwargs["market_wide_impact_pct"] = Decimal(str(market_wide_impact_pct))
    if status:
        kwargs["status"] = status
    elif kwargs.get("scheduled_at") and not kwargs.get("is_released"):
        kwargs["status"] = "scheduled"
    else:
        kwargs.setdefault("status", "draft")
    event = NewsEvent(**kwargs)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def release_news(db: Session, event_id: int, *, now: datetime | None = None) -> NewsEvent:
    event = db.get(NewsEvent, event_id)
    if event is None:
        raise ValueError("news not found")
    if event.status == "cancelled":
        raise ValueError("news was cancelled")
    now = now or datetime.now(timezone.utc)
    event.is_released = True
    event.released_at = now
    event.status = "released"
    snapshot_baselines_on_release(db, event)
    from app.services.news_impact_resolver import compute_stock_impacts_for_news

    compute_stock_impacts_for_news(db, event)

    # Optional fair-value nudge from targets (does NOT set LTP)
    stocks = list(
        db.scalars(select(Stock).options(joinedload(Stock.market_sector))).all()
    )
    from app.services.news_impact_resolver import target_impact_pct_for_stock

    settings = get_settings()
    for stock in stocks:
        pct = target_impact_pct_for_stock(db, event, stock)
        if pct is None:
            continue
        # Soft fair-value shift toward target (AI trades move LTP)
        factor = Decimal("1") + (
            Decimal(str(pct))
            * Decimal(str(settings.news_fundamental_multiplier))
            / Decimal("100")
            * Decimal("0.35")
        )
        stock.fair_value = (stock.fair_value * factor).quantize(Decimal("0.0001"))

    db.commit()
    db.refresh(event)
    return event


def cancel_news(db: Session, event_id: int) -> NewsEvent:
    event = db.get(NewsEvent, event_id)
    if event is None:
        raise ValueError("news not found")
    if event.is_released:
        raise ValueError("cannot cancel released news")
    event.status = "cancelled"
    db.commit()
    db.refresh(event)
    return event


def release_due_scheduled(db: Session) -> list[NewsEvent]:
    now = datetime.now(timezone.utc)
    rows = list(
        db.scalars(
            select(NewsEvent).where(
                NewsEvent.status == "scheduled",
                NewsEvent.is_released.is_(False),
                NewsEvent.scheduled_at.is_not(None),
                NewsEvent.scheduled_at <= now,
            )
        ).all()
    )
    out = []
    for event in rows:
        out.append(release_news(db, event.id, now=now))
    return out


def list_news(
    db: Session,
    *,
    released_only: bool = False,
    include_scheduled: bool = False,
) -> list[NewsEvent]:
    stmt = select(NewsEvent).order_by(NewsEvent.id.desc())
    if released_only:
        stmt = stmt.where(NewsEvent.is_released.is_(True))
    elif not include_scheduled:
        stmt = stmt.where(NewsEvent.status != "cancelled")
    return list(db.scalars(stmt).all())


def get_news(db: Session, news_id: int) -> NewsEvent | None:
    return db.get(NewsEvent, news_id)


def news_detail_dict(event: NewsEvent) -> dict:
    try:
        sector_impacts = json.loads(event.sector_impacts_json or "{}")
    except json.JSONDecodeError:
        sector_impacts = {}
    try:
        stock_impacts = json.loads(event.stock_impacts_json or "{}")
    except json.JSONDecodeError:
        stock_impacts = {}
    try:
        brief_points = json.loads(event.brief_points_json or "[]")
    except json.JSONDecodeError:
        brief_points = []
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "brief_points": brief_points,
        "affected_tickers": event.affected_tickers,
        "affected_sectors": event.affected_sectors,
        "market_wide": event.market_wide,
        "direction": event.direction,
        "impact": str(event.impact),
        "confidence": str(event.confidence),
        "duration_minutes": event.duration_minutes,
        "decay_rate": str(event.decay_rate),
        "fundamental_impact_pct": (
            str(event.fundamental_impact_pct) if event.fundamental_impact_pct is not None else None
        ),
        "market_wide_impact_pct": (
            str(event.market_wide_impact_pct) if event.market_wide_impact_pct is not None else None
        ),
        "sector_impacts": sector_impacts,
        "stock_impacts": stock_impacts,
        "status": event.status,
        "is_released": event.is_released,
        "released_at": event.released_at.isoformat() if event.released_at else None,
        "scheduled_at": event.scheduled_at.isoformat() if event.scheduled_at else None,
        "effective_impact": str(effective_impact(event)),
    }


def news_pressure_for_ticker(db: Session, ticker: str, *, now: datetime | None = None) -> Decimal:
    """Normalized news pressure for a ticker (amplified for event volatility)."""
    settings = get_settings()
    stock = db.scalar(
        select(Stock)
        .options(joinedload(Stock.market_sector))
        .where(Stock.ticker == ticker.upper())
    )
    events = list_news(db, released_only=True)
    total = Decimal("0")
    from app.services.news_impact_resolver import sector_impact_for_stock

    for event in events:
        tickers = [t.strip().upper() for t in event.affected_tickers.split(",") if t.strip()]
        if event.market_wide or ticker.upper() in tickers:
            total += effective_impact(event, now=now)
            continue
        if stock is not None:
            sector_pct = sector_impact_for_stock(event, stock)
            if sector_pct is not None:
                base = effective_impact(event, now=now)
                magnitude = Decimal(str(1 + min(abs(sector_pct) / 10.0, 3.0)))
                sign = Decimal("1") if sector_pct >= 0 else Decimal("-1")
                total += base * magnitude * sign
                continue
        # sector / JSON impacts also count
        try:
            stocks_map = json.loads(event.stock_impacts_json or "{}")
            if ticker.lower() in {k.lower() for k in stocks_map}:
                total += effective_impact(event, now=now)
        except json.JSONDecodeError:
            pass
    total *= Decimal(str(settings.news_pressure_amplifier))
    cap = Decimal(str(settings.news_pressure_cap))
    if total > cap:
        return cap
    if total < -cap:
        return -cap
    return total
