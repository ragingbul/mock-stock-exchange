"""Default fictional stock universe (configurable seed data)."""

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

DEFAULT_STOCKS: list[StockCreate] = [
    StockCreate(
        ticker="TECHNOVA",
        company_name="TechNova Systems",
        sector=Sector.TECH,
        starting_price=Decimal("100.00"),
        shares_outstanding=50_000_000,
        fair_value=Decimal("105.00"),
        volatility_class=VolatilityClass.HIGH,
        liquidity_class=LiquidityClass.HIGH,
        fundamental_profile=FundamentalProfile.GROWTH,
        description="Enterprise software and cloud services.",
    ),
    StockCreate(
        ticker="AUTOMAX",
        company_name="AutoMax Motors",
        sector=Sector.AUTO,
        starting_price=Decimal("85.00"),
        shares_outstanding=40_000_000,
        fair_value=Decimal("88.00"),
        volatility_class=VolatilityClass.MEDIUM,
        liquidity_class=LiquidityClass.MEDIUM,
        fundamental_profile=FundamentalProfile.CYCLICAL,
        description="Passenger vehicles and EV components.",
    ),
    StockCreate(
        ticker="GREENPOWER",
        company_name="GreenPower Energy",
        sector=Sector.ENERGY,
        starting_price=Decimal("62.50"),
        shares_outstanding=35_000_000,
        fair_value=Decimal("70.00"),
        volatility_class=VolatilityClass.HIGH,
        liquidity_class=LiquidityClass.MEDIUM,
        fundamental_profile=FundamentalProfile.GROWTH,
        description="Renewable power generation.",
    ),
    StockCreate(
        ticker="FINBANK",
        company_name="FinBank Holdings",
        sector=Sector.FINANCE,
        starting_price=Decimal("210.00"),
        shares_outstanding=80_000_000,
        fair_value=Decimal("215.00"),
        volatility_class=VolatilityClass.LOW,
        liquidity_class=LiquidityClass.HIGH,
        fundamental_profile=FundamentalProfile.STABLE,
        description="Retail and corporate banking.",
    ),
    StockCreate(
        ticker="PHARMEX",
        company_name="PharmEx Labs",
        sector=Sector.PHARMA,
        starting_price=Decimal("145.00"),
        shares_outstanding=25_000_000,
        fair_value=Decimal("150.00"),
        volatility_class=VolatilityClass.MEDIUM,
        liquidity_class=LiquidityClass.MEDIUM,
        fundamental_profile=FundamentalProfile.GROWTH,
        description="Generic and specialty pharmaceuticals.",
    ),
    StockCreate(
        ticker="RETAILCO",
        company_name="RetailCo Markets",
        sector=Sector.RETAIL,
        starting_price=Decimal("48.00"),
        shares_outstanding=60_000_000,
        fair_value=Decimal("50.00"),
        volatility_class=VolatilityClass.MEDIUM,
        liquidity_class=LiquidityClass.HIGH,
        fundamental_profile=FundamentalProfile.CYCLICAL,
        description="Nationwide retail chain.",
    ),
    StockCreate(
        ticker="ENERGYX",
        company_name="EnergyX Oil & Gas",
        sector=Sector.ENERGY,
        starting_price=Decimal("175.00"),
        shares_outstanding=45_000_000,
        fair_value=Decimal("168.00"),
        volatility_class=VolatilityClass.HIGH,
        liquidity_class=LiquidityClass.MEDIUM,
        fundamental_profile=FundamentalProfile.CYCLICAL,
        description="Upstream energy producer.",
    ),
    StockCreate(
        ticker="DATACORE",
        company_name="DataCore Analytics",
        sector=Sector.DATA,
        starting_price=Decimal("132.00"),
        shares_outstanding=20_000_000,
        fair_value=Decimal("140.00"),
        volatility_class=VolatilityClass.HIGH,
        liquidity_class=LiquidityClass.MEDIUM,
        fundamental_profile=FundamentalProfile.GROWTH,
        description="Data infrastructure and analytics.",
    ),
    StockCreate(
        ticker="INFRAONE",
        company_name="InfraOne Projects",
        sector=Sector.INFRA,
        starting_price=Decimal("95.00"),
        shares_outstanding=30_000_000,
        fair_value=Decimal("98.00"),
        volatility_class=VolatilityClass.LOW,
        liquidity_class=LiquidityClass.LOW,
        fundamental_profile=FundamentalProfile.STABLE,
        description="Infrastructure construction.",
    ),
    StockCreate(
        ticker="FOODCORP",
        company_name="FoodCorp Industries",
        sector=Sector.FOOD,
        starting_price=Decimal("72.00"),
        shares_outstanding=55_000_000,
        fair_value=Decimal("74.00"),
        volatility_class=VolatilityClass.LOW,
        liquidity_class=LiquidityClass.HIGH,
        fundamental_profile=FundamentalProfile.STABLE,
        description="Packaged foods and distribution.",
    ),
]


def seed_default_stocks(db: Session, *, skip_existing: bool = True) -> int:
    """Insert default stocks. Returns count of newly created rows."""
    from app.services import sector_service

    sector_service.ensure_sectors(db)
    created = 0
    for spec in DEFAULT_STOCKS:
        existing = stock_service.get_stock_by_ticker(db, spec.ticker)
        if existing and skip_existing:
            continue
        if existing and not skip_existing:
            continue
        stock_service.create_stock(db, spec)
        created += 1
    sector_service.backfill_stock_sectors(db)
    return created
