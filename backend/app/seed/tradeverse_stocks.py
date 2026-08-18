"""TRADEVERSE 40-company universe — hybrid NSE tickers + simplified display names."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import (
    FundamentalProfile,
    LiquidityClass,
    Sector,
    VolatilityClass,
)
from app.schemas import StockCreate
from app.services import stock_service

# (ticker, display name, sector_enum, price, volatility)
TRADEVERSE_TRADABLE_STOCKS: list[tuple[str, str, Sector, str, VolatilityClass]] = [
    # Financials (5)
    ("AXISBANK", "Axis Bank", Sector.FINANCE, "280.00", VolatilityClass.HIGH),
    ("HDFCBANK", "HDFC Bank", Sector.FINANCE, "220.00", VolatilityClass.HIGH),
    ("ICICIBANK", "ICICI Bank", Sector.FINANCE, "180.00", VolatilityClass.VERY_HIGH),
    ("PNB", "Punjab National Bank", Sector.FINANCE, "650.00", VolatilityClass.HIGH),
    ("SBIN", "State Bank of India", Sector.FINANCE, "1200.00", VolatilityClass.HIGH),
    # IT (5)
    ("HCLTECH", "HCL Technologies", Sector.TECH, "180.00", VolatilityClass.MEDIUM),
    ("INFOSYSTCH", "Infosys", Sector.TECH, "1400.00", VolatilityClass.MEDIUM),
    ("SATYAMCOMP", "Satyam Computer", Sector.TECH, "350.00", VolatilityClass.HIGH),
    ("TCS", "Tata Consultancy", Sector.TECH, "850.00", VolatilityClass.MEDIUM),
    ("WIPRO", "Wipro", Sector.TECH, "240.00", VolatilityClass.MEDIUM),
    # Automobiles (5)
    ("BAJAJAUTO", "Bajaj Auto", Sector.AUTO, "2100.00", VolatilityClass.HIGH),
    ("HEROHONDA", "Hero Honda", Sector.AUTO, "850.00", VolatilityClass.HIGH),
    ("MARUTI", "Maruti Motors", Sector.AUTO, "950.00", VolatilityClass.HIGH),
    ("M&M", "Mahindra & Mahindra", Sector.AUTO, "680.00", VolatilityClass.HIGH),
    ("TATAMOTORS", "Tata Motors", Sector.AUTO, "720.00", VolatilityClass.HIGH),
    # Energy (7)
    ("BPCL", "Bharat Petroleum", Sector.ENERGY, "380.00", VolatilityClass.MEDIUM),
    ("GAIL", "GAIL India", Sector.ENERGY, "340.00", VolatilityClass.MEDIUM),
    ("NTPC", "NTPC", Sector.ENERGY, "180.00", VolatilityClass.LOW),
    ("ONGC", "ONGC", Sector.ENERGY, "1100.00", VolatilityClass.MEDIUM),
    ("RELIANCE", "Reliance Energy", Sector.ENERGY, "2100.00", VolatilityClass.HIGH),
    ("TATAPOWER", "Tata Power", Sector.ENERGY, "180.00", VolatilityClass.MEDIUM),
    ("RPETRO", "Reliance Petroleum", Sector.ENERGY, "120.00", VolatilityClass.HIGH),
    # Industrials (4)
    ("ABB", "ABB India", Sector.INDUSTRIALS, "920.00", VolatilityClass.HIGH),
    ("BHEL", "BHEL", Sector.INDUSTRIALS, "2100.00", VolatilityClass.HIGH),
    ("LT", "Larsen & Toubro", Sector.INDUSTRIALS, "4200.00", VolatilityClass.HIGH),
    ("SIEMENS", "Siemens", Sector.INDUSTRIALS, "780.00", VolatilityClass.HIGH),
    # Infrastructure (2)
    ("GMRINFRA", "GMR Infra", Sector.INFRA, "45.00", VolatilityClass.VERY_HIGH),
    ("JPASSOCIAT", "Jaiprakash Associates", Sector.INFRA, "220.00", VolatilityClass.VERY_HIGH),
    # Real Estate (1)
    ("UNITECH", "Unitech", Sector.REAL_ESTATE, "420.00", VolatilityClass.VERY_HIGH),
    # Metals (5)
    ("HINDALCO", "Hindalco", Sector.INDUSTRIALS, "180.00", VolatilityClass.VERY_HIGH),
    ("SAIL", "SAIL", Sector.INDUSTRIALS, "580.00", VolatilityClass.VERY_HIGH),
    ("TATASTEEL", "Tata Steel", Sector.INDUSTRIALS, "620.00", VolatilityClass.VERY_HIGH),
    ("STER", "Sterlite Industries", Sector.INDUSTRIALS, "520.00", VolatilityClass.VERY_HIGH),
    ("NATIONALUM", "National Aluminium", Sector.INDUSTRIALS, "240.00", VolatilityClass.VERY_HIGH),
    # Consumer (1)
    ("ITC", "ITC", Sector.RETAIL, "180.00", VolatilityClass.LOW),
]

TRADEVERSE_IPO_TICKERS: frozenset[str] = frozenset(
    {"RPOWER", "FCH", "JKIL", "CORDSCABLE", "20MICRONS"}
)

TRADEVERSE_IPO_DEFINITIONS: list[dict] = [
    {
        "ticker": "FCH",
        "company_name": "Future Capital",
        "sector_slug": "financials",
        "issue_price": 765,
    },
    {
        "ticker": "RPOWER",
        "company_name": "Reliance Power",
        "sector_slug": "infrastructure",
        "issue_price": 450,
    },
    {
        "ticker": "JKIL",
        "company_name": "J Kumar Infra",
        "sector_slug": "infrastructure",
        "issue_price": 110,
    },
    {
        "ticker": "CORDSCABLE",
        "company_name": "Cords Cable",
        "sector_slug": "industrials",
        "issue_price": 135,
    },
    {
        "ticker": "20MICRONS",
        "company_name": "20 Microns",
        "sector_slug": "metals",
        "issue_price": 55,
    },
]

# Backward-compatible alias — tradable count at RESET
TRADEVERSE_STOCKS = TRADEVERSE_TRADABLE_STOCKS

# Explicit ticker → sector slug overrides (metals use INDUSTRIALS enum)
TICKER_SECTOR_SLUG: dict[str, str] = {
    "HINDALCO": "metals",
    "SAIL": "metals",
    "TATASTEEL": "metals",
    "STER": "metals",
    "NATIONALUM": "metals",
}


def canonical_tradable_count() -> int:
    return len(TRADEVERSE_TRADABLE_STOCKS)


def canonical_ipo_count() -> int:
    return len(TRADEVERSE_IPO_DEFINITIONS)


def canonical_total_count() -> int:
    return canonical_tradable_count() + canonical_ipo_count()


def canonical_tradable_tickers() -> frozenset[str]:
    return frozenset(ticker for ticker, *_ in TRADEVERSE_TRADABLE_STOCKS)


def ipo_definition_by_ticker(ticker: str) -> dict | None:
    key = ticker.strip().upper()
    for row in TRADEVERSE_IPO_DEFINITIONS:
        if row["ticker"] == key:
            return row
    return None


def resolve_ipo_sector_id(db: Session, ticker: str) -> int | None:
    from app.services import sector_service

    defn = ipo_definition_by_ticker(ticker)
    if defn is None:
        return None
    sector = sector_service.get_sector_by_slug(db, defn["sector_slug"])
    return sector.id if sector else None


def sector_slug_for_ticker(ticker: str, sector_enum: Sector) -> str:
    from app.services.sector_service import ENUM_TO_SECTOR_SLUG

    override = TICKER_SECTOR_SLUG.get(ticker.upper())
    if override:
        return override
    return ENUM_TO_SECTOR_SLUG.get(sector_enum.value, sector_enum.value)


def seed_tradeverse_stocks(db: Session, *, skip_existing: bool = True) -> int:
    from app.services import sector_service

    sector_service.ensure_sectors(db)
    created = 0
    for ticker, name, sector, price_s, vol in TRADEVERSE_TRADABLE_STOCKS:
        if stock_service.get_stock_by_ticker(db, ticker) and skip_existing:
            continue
        if stock_service.get_stock_by_ticker(db, ticker):
            continue
        price = Decimal(price_s)
        slug = sector_slug_for_ticker(ticker, sector)
        sector_row = sector_service.get_sector_by_slug(db, slug)
        stock_service.create_stock(
            db,
            StockCreate(
                ticker=ticker,
                company_name=name,
                sector=sector,
                sector_id=sector_row.id if sector_row else None,
                starting_price=price,
                shares_outstanding=50_000_000,
                fair_value=price,
                volatility_class=vol,
                liquidity_class=LiquidityClass.MEDIUM,
                fundamental_profile=FundamentalProfile.CYCLICAL,
                description=f"TRADEVERSE — {name}",
            ),
        )
        created += 1
    sector_service.backfill_stock_sectors(db)
    return created
