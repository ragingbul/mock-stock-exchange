"""Sector catalogue, stock assignment, and sector performance summaries."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Stock
from app.models.enums import Sector
from app.models.sector import MarketSector

# Spec display sectors (slug, name, display_order)
DEFAULT_SECTORS: list[tuple[str, str, int]] = [
    ("financials", "Financials", 1),
    ("technology", "Technology", 2),
    ("energy", "Energy", 3),
    ("healthcare", "Healthcare", 4),
    ("consumer", "Consumer", 5),
    ("industrials", "Industrials", 6),
    ("real_estate", "Real Estate", 7),
    ("utilities", "Utilities", 8),
    ("telecommunications", "Telecommunications", 9),
    ("automotive", "Automotive", 10),
]

# Map legacy Stock.sector enum values → MarketSector.slug
ENUM_TO_SECTOR_SLUG: dict[str, str] = {
    "tech": "technology",
    "data": "technology",
    "finance": "financials",
    "financials": "financials",
    "energy": "energy",
    "pharma": "healthcare",
    "healthcare": "healthcare",
    "retail": "consumer",
    "food": "consumer",
    "consumer": "consumer",
    "infra": "industrials",
    "industrials": "industrials",
    "auto": "automotive",
    "automotive": "automotive",
    "real_estate": "real_estate",
    "utilities": "utilities",
    "telecom": "telecommunications",
    "technology": "technology",
}

# Prefer a stable enum when assigning from a sector slug (for news matching)
SLUG_TO_ENUM: dict[str, Sector] = {
    "technology": Sector.TECH,
    "financials": Sector.FINANCE,
    "energy": Sector.ENERGY,
    "healthcare": Sector.PHARMA,
    "consumer": Sector.RETAIL,
    "industrials": Sector.INFRA,
    "automotive": Sector.AUTO,
    "real_estate": Sector.REAL_ESTATE,
    "utilities": Sector.UTILITIES,
    "telecommunications": Sector.TELECOM,
}


class SectorServiceError(Exception):
    """Domain error for sector operations."""


def seed_default_sectors(db: Session) -> int:
    """Insert default sectors. Returns count of newly created rows."""
    created = 0
    for slug, name, order in DEFAULT_SECTORS:
        existing = db.scalar(select(MarketSector).where(MarketSector.slug == slug))
        if existing:
            continue
        db.add(MarketSector(slug=slug, name=name, display_order=order, is_active=True))
        created += 1
    if created:
        db.commit()
    return created


def ensure_sectors(db: Session) -> None:
    seed_default_sectors(db)


def get_sector(db: Session, sector_id: int) -> MarketSector | None:
    return db.get(MarketSector, sector_id)


def get_sector_by_slug(db: Session, slug: str) -> MarketSector | None:
    return db.scalar(
        select(MarketSector).where(MarketSector.slug == slug.strip().lower())
    )


def list_sectors(db: Session, *, active_only: bool = True) -> list[MarketSector]:
    stmt = select(MarketSector).order_by(MarketSector.display_order, MarketSector.name)
    if active_only:
        stmt = stmt.where(MarketSector.is_active.is_(True))
    return list(db.scalars(stmt).all())


def resolve_sector_for_enum(db: Session, sector: Sector) -> MarketSector | None:
    ensure_sectors(db)
    slug = ENUM_TO_SECTOR_SLUG.get(sector.value, sector.value)
    return get_sector_by_slug(db, slug)


def assign_stock_sector(
    db: Session,
    stock_id: int,
    *,
    sector_id: int | None = None,
    sector_slug: str | None = None,
) -> Stock:
    stock = db.get(Stock, stock_id)
    if stock is None:
        raise SectorServiceError(f"stock not found: {stock_id}")

    ensure_sectors(db)
    sector: MarketSector | None = None
    if sector_id is not None:
        sector = get_sector(db, sector_id)
    elif sector_slug:
        sector = get_sector_by_slug(db, sector_slug)
    if sector is None:
        raise SectorServiceError("sector not found")

    stock.sector_id = sector.id
    enum_val = SLUG_TO_ENUM.get(sector.slug)
    if enum_val is not None:
        stock.sector = enum_val
    db.commit()
    db.refresh(stock)
    return stock


def link_stock_to_sector(db: Session, stock: Stock) -> None:
    """Ensure stock.sector_id is set from its enum code."""
    if stock.sector_id is not None:
        return
    sector = resolve_sector_for_enum(db, stock.sector)
    if sector is not None:
        stock.sector_id = sector.id


def list_stocks_in_sector(db: Session, sector_id: int) -> list[Stock]:
    return list(
        db.scalars(
            select(Stock)
            .where(Stock.sector_id == sector_id)
            .order_by(Stock.ticker)
        ).all()
    )


def _percent_change(stock: Stock) -> Decimal:
    previous = Decimal(stock.previous_close)
    last = Decimal(stock.last_traded_price)
    if previous <= 0:
        return Decimal("0")
    return ((last - previous) / previous) * Decimal("100")


def sector_summary(db: Session, sector_id: int | None = None) -> list[dict]:
    """Performance summary per sector (or one sector)."""
    ensure_sectors(db)
    stmt = select(MarketSector).options(joinedload(MarketSector.stocks))
    if sector_id is not None:
        stmt = stmt.where(MarketSector.id == sector_id)
    stmt = stmt.order_by(MarketSector.display_order, MarketSector.name)
    sectors = list(db.scalars(stmt).unique().all())

    out: list[dict] = []
    for sector in sectors:
        stocks = [s for s in sector.stocks if s.is_open]
        if not stocks:
            out.append(
                {
                    "sector_id": sector.id,
                    "slug": sector.slug,
                    "name": sector.name,
                    "stock_count": 0,
                    "sector_change_pct": "0.0000",
                    "top_gainer": None,
                    "top_loser": None,
                    "stocks": [],
                }
            )
            continue

        rows = []
        for stock in stocks:
            pct = _percent_change(stock).quantize(Decimal("0.0001"))
            rows.append(
                {
                    "stock_id": stock.id,
                    "ticker": stock.ticker,
                    "company_name": stock.company_name,
                    "last_traded_price": str(stock.last_traded_price),
                    "percent_change": str(pct),
                }
            )
        avg = (sum((_percent_change(s) for s in stocks), Decimal("0")) / len(stocks)).quantize(
            Decimal("0.0001")
        )
        ranked = sorted(rows, key=lambda r: Decimal(r["percent_change"]), reverse=True)
        out.append(
            {
                "sector_id": sector.id,
                "slug": sector.slug,
                "name": sector.name,
                "stock_count": len(stocks),
                "sector_change_pct": str(avg),
                "top_gainer": ranked[0],
                "top_loser": ranked[-1],
                "stocks": ranked,
            }
        )
    return out


def backfill_stock_sectors(db: Session) -> int:
    """Link existing stocks missing sector_id. Returns updated count."""
    ensure_sectors(db)
    updated = 0
    stocks = list(db.scalars(select(Stock).where(Stock.sector_id.is_(None))).all())
    for stock in stocks:
        sector = resolve_sector_for_enum(db, stock.sector)
        if sector is None:
            continue
        stock.sector_id = sector.id
        updated += 1
    if updated:
        db.commit()
    return updated
