"""Resolve per-stock news target impacts (stock > sector > market-wide)."""

from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models import NewsEvent, Stock
from app.services import sector_service
from app.services.simulation_settings_service import get_or_create_settings


def _parse_map(raw: str | None) -> dict[str, float]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k).lower(): float(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return {}


def target_impact_pct_for_stock(event: NewsEvent, stock: Stock) -> float | None:
    """Return intended % move for this stock from one news event, or None if unaffected."""
    stock_map = _parse_map(event.stock_impacts_json)
    if stock.ticker.lower() in stock_map:
        return stock_map[stock.ticker.lower()]
    # also allow exact ticker case
    if stock.ticker in _parse_map(event.stock_impacts_json):
        return float(_parse_map(event.stock_impacts_json)[stock.ticker])

    sector_map = _parse_map(event.sector_impacts_json)
    slug = None
    if stock.market_sector is not None:
        slug = stock.market_sector.slug
    else:
        slug = sector_service.ENUM_TO_SECTOR_SLUG.get(stock.sector.value)
    if slug and slug in sector_map:
        return sector_map[slug]
    # legacy affected_sectors comma list + fundamental_impact_pct / impact*direction
    sectors = [s.strip().lower() for s in (event.affected_sectors or "").split(",") if s.strip()]
    tickers = [t.strip().upper() for t in (event.affected_tickers or "").split(",") if t.strip()]
    affected = event.market_wide or stock.ticker in tickers
    if slug and slug in sectors:
        affected = True
    if stock.sector.value in sectors:
        affected = True
    if not affected:
        return None

    if event.market_wide_impact_pct is not None:
        return float(event.market_wide_impact_pct)
    if event.fundamental_impact_pct is not None:
        return float(event.fundamental_impact_pct)
    # fallback: direction * impact * 100 * confidence (scaled to percent points)
    return float(event.direction) * float(event.impact) * float(event.confidence) * 8.0


def combined_target_for_stock(db: Session, stock: Stock) -> dict:
    """Aggregate active news targets for a stock with clamping."""
    settings = get_or_create_settings(db)
    events = list(
        db.scalars(
            select(NewsEvent).where(
                NewsEvent.is_released.is_(True),
                NewsEvent.status != "cancelled",
            )
        ).all()
    )
    # Prefer stocks with sector loaded
    stock = db.scalar(
        select(Stock).where(Stock.id == stock.id).options(joinedload(Stock.market_sector))
    ) or stock

    targets: list[float] = []
    baselines: dict[str, float] = {}
    for event in events:
        t = target_impact_pct_for_stock(event, stock)
        if t is None:
            continue
        targets.append(t)
        try:
            base = json.loads(event.baseline_prices_json or "{}")
            if stock.ticker in base:
                baselines[stock.ticker] = float(base[stock.ticker])
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    if not targets:
        return {
            "target_impact_pct": 0.0,
            "current_impact_pct": 0.0,
            "remaining_impact_pct": 0.0,
            "reached": True,
            "active_news": 0,
        }

    raw = sum(targets)
    cap = float(settings.news_combined_impact_cap_pct)
    target = max(-cap, min(cap, raw))

    baseline = baselines.get(stock.ticker)
    if baseline is None or baseline <= 0:
        baseline = float(stock.previous_close or stock.starting_price)
    current_px = float(stock.last_traded_price)
    current = ((current_px - baseline) / baseline) * 100.0 if baseline else 0.0
    remaining = target - current
    tol = float(settings.news_impact_tolerance_pct)
    reached = abs(remaining) <= tol

    return {
        "target_impact_pct": round(target, 4),
        "current_impact_pct": round(current, 4),
        "remaining_impact_pct": round(remaining, 4),
        "reached": reached,
        "tolerance_pct": tol,
        "active_news": len(targets),
        "baseline_price": baseline,
    }


def snapshot_baselines_on_release(db: Session, event: NewsEvent) -> None:
    stocks = list(db.scalars(select(Stock)).all())
    mapping = {s.ticker: str(s.last_traded_price) for s in stocks}
    event.baseline_prices_json = json.dumps(mapping)
