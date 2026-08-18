"""Resolve per-stock news target impacts — sector-first with deterministic ±5% variation."""

from __future__ import annotations

import json
import random
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import NewsEvent, Stock
from app.models.news_stock_impact import NewsStockImpact
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


# Normalize timeline sector names → slug keys
SECTOR_ALIASES: dict[str, str] = {
    "financials": "financials",
    "it": "it",
    "technology": "it",
    "automobiles": "automobiles",
    "automotive": "automobiles",
    "energy": "energy",
    "industrials": "industrials",
    "infrastructure": "infrastructure",
    "infra": "infrastructure",
    "real estate": "real_estate",
    "real_estate": "real_estate",
    "metals": "metals",
    "consumer": "consumer",
    "healthcare": "consumer",
    "broad market": "broad_market",
    "broad_market": "broad_market",
    "power / infrastructure": "infrastructure",
    "financial services": "financials",
    "manufacturing": "industrials",
    "industrial minerals": "metals",
}


def _stock_sector_slug(stock: Stock) -> str | None:
    if stock.market_sector is not None:
        return stock.market_sector.slug
    mapped = sector_service.ENUM_TO_SECTOR_SLUG.get(stock.sector.value)
    return mapped


def seeded_variation(stock_id: int, news_event_id: int, seed: int) -> float:
    """Deterministic variation in [-0.05, +0.05] relative to sector impact."""
    rng = random.Random(seed ^ (stock_id * 1_000_003 + news_event_id * 9_176))
    return rng.uniform(-0.05, 0.05)


def sector_impact_for_stock(event: NewsEvent, stock: Stock) -> float | None:
    """Sector-first impact — ignores stock-specific JSON to avoid double application."""
    sector_map_raw = _parse_map(event.sector_impacts_json)
    sector_map = {SECTOR_ALIASES.get(k, k): v for k, v in sector_map_raw.items()}

    slug = _stock_sector_slug(stock)
    if slug and slug in sector_map:
        return sector_map[slug]

    if event.market_wide_impact_pct is not None:
        return float(event.market_wide_impact_pct)

    market_wide = sector_map.get("broad_market")
    if market_wide is not None:
        return market_wide

    return None


def compute_stock_impacts_for_news(db: Session, event: NewsEvent) -> int:
    """Create fixed NewsStockImpact rows once at news release."""
    from sqlalchemy.orm import joinedload as sa_joinedload

    settings = get_or_create_settings(db)
    seed = int(settings.simulation_seed)
    stocks = list(
        db.scalars(select(Stock).options(sa_joinedload(Stock.market_sector))).all()
    )
    created = 0
    for stock in stocks:
        sector_pct = sector_impact_for_stock(event, stock)
        if sector_pct is None:
            continue
        existing = db.scalar(
            select(NewsStockImpact).where(
                NewsStockImpact.news_event_id == event.id,
                NewsStockImpact.stock_id == stock.id,
            )
        )
        if existing:
            continue
        ref = Decimal(stock.last_traded_price or stock.starting_price)
        variation = Decimal(str(seeded_variation(stock.id, event.id, seed)))
        target_pct = Decimal(str(sector_pct)) * (Decimal("1") + variation)
        target_price = ref * (Decimal("1") + target_pct / Decimal("100"))
        slug = _stock_sector_slug(stock) or "unknown"
        db.add(
            NewsStockImpact(
                news_event_id=event.id,
                stock_id=stock.id,
                sector_slug=slug,
                sector_impact_pct=Decimal(str(sector_pct)),
                variation_pct=variation,
                target_impact_pct=target_pct,
                reference_price=ref,
                target_price=target_price,
            )
        )
        created += 1
    db.commit()
    return created


def target_impact_pct_for_stock(db: Session, event: NewsEvent, stock: Stock) -> float | None:
    row = db.scalar(
        select(NewsStockImpact).where(
            NewsStockImpact.news_event_id == event.id,
            NewsStockImpact.stock_id == stock.id,
        )
    )
    if row is not None:
        return float(row.target_impact_pct)
    sector_pct = sector_impact_for_stock(event, stock)
    if sector_pct is None:
        return None
    settings = get_or_create_settings(db)
    variation = seeded_variation(stock.id, event.id, int(settings.simulation_seed))
    return sector_pct * (1.0 + variation)


def combined_target_for_stock(db: Session, stock: Stock) -> dict:
    """Aggregate active news targets with ±15% combined cap."""
    settings = get_or_create_settings(db)
    from sqlalchemy.orm import joinedload as sa_joinedload

    stock = db.scalar(
        select(Stock).where(Stock.id == stock.id).options(sa_joinedload(Stock.market_sector))
    ) or stock

    impacts = list(
        db.scalars(
            select(NewsStockImpact)
            .join(NewsEvent, NewsEvent.id == NewsStockImpact.news_event_id)
            .where(
                NewsStockImpact.stock_id == stock.id,
                NewsEvent.is_released.is_(True),
                NewsEvent.status != "cancelled",
            )
            .order_by(NewsStockImpact.id)
        ).all()
    )

    if not impacts:
        return {
            "target_impact_pct": 0.0,
            "current_impact_pct": 0.0,
            "remaining_impact_pct": 0.0,
            "reached": True,
            "active_news": 0,
            "baseline_price": float(stock.starting_price),
        }

    targets = [float(i.target_impact_pct) for i in impacts]
    cap = float(settings.news_combined_impact_cap_pct)
    target = max(-cap, min(cap, sum(targets)))

    baseline = float(impacts[0].reference_price)
    current_px = float(stock.last_traded_price or stock.starting_price)
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
        "active_news": len(impacts),
        "baseline_price": baseline,
    }


def snapshot_baselines_on_release(db: Session, event: NewsEvent) -> None:
    stocks = list(db.scalars(select(Stock)).all())
    mapping = {s.ticker: str(s.last_traded_price or s.starting_price) for s in stocks}
    event.baseline_prices_json = json.dumps(mapping)
