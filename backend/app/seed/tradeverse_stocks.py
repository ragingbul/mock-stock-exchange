"""~40 fictional TRADEVERSE stocks across 9 simulation sectors."""

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

# (ticker, name, sector_enum, price, volatility)
TRADEVERSE_STOCKS: list[tuple[str, str, Sector, str, VolatilityClass]] = [
    # Financials (6)
    ("FINBANK", "FinBank Holdings", Sector.FINANCE, "210.00", VolatilityClass.LOW),
    ("CAPONE", "CapOne Financial", Sector.FINANCE, "145.00", VolatilityClass.MEDIUM),
    ("TRUSTCO", "TrustCo Bank", Sector.FINANCE, "98.50", VolatilityClass.MEDIUM),
    ("MORTGAGE", "MortgageMax", Sector.FINANCE, "72.00", VolatilityClass.HIGH),
    ("INVESTBK", "InvestBank Corp", Sector.FINANCE, "188.00", VolatilityClass.MEDIUM),
    ("LEHMANX", "LehmanX Capital", Sector.FINANCE, "120.00", VolatilityClass.VERY_HIGH),
    # IT (5)
    ("TECHNOVA", "TechNova Systems", Sector.TECH, "100.00", VolatilityClass.HIGH),
    ("DATACORE", "DataCore Analytics", Sector.DATA, "132.00", VolatilityClass.HIGH),
    ("SOFTWAVE", "SoftWave Inc", Sector.TECH, "88.00", VolatilityClass.MEDIUM),
    ("CLOUDEX", "CloudEx Services", Sector.TECH, "156.00", VolatilityClass.HIGH),
    ("CYBERIQ", "CyberIQ Labs", Sector.TECH, "74.00", VolatilityClass.VERY_HIGH),
    # Automobiles (4)
    ("AUTOMAX", "AutoMax Motors", Sector.AUTO, "85.00", VolatilityClass.MEDIUM),
    ("DRIVECO", "DriveCo Vehicles", Sector.AUTO, "62.00", VolatilityClass.MEDIUM),
    ("EVPOWER", "EVPower Auto", Sector.AUTO, "48.00", VolatilityClass.HIGH),
    ("WHEELCO", "WheelCo Industries", Sector.AUTO, "55.00", VolatilityClass.MEDIUM),
    # Energy (4)
    ("ENERGYX", "EnergyX Oil & Gas", Sector.ENERGY, "175.00", VolatilityClass.HIGH),
    ("GREENPOWER", "GreenPower Energy", Sector.ENERGY, "62.50", VolatilityClass.HIGH),
    ("PETROMAX", "PetroMax Refining", Sector.ENERGY, "142.00", VolatilityClass.MEDIUM),
    ("SOLARCO", "SolarCo Renewables", Sector.ENERGY, "38.00", VolatilityClass.HIGH),
    # Industrials (5)
    ("INFRAONE", "InfraOne Projects", Sector.INFRA, "95.00", VolatilityClass.LOW),
    ("STEELCO", "SteelCo Manufacturing", Sector.INDUSTRIALS, "112.00", VolatilityClass.MEDIUM),
    ("HEAVYMCH", "HeavyMach Corp", Sector.INDUSTRIALS, "78.00", VolatilityClass.MEDIUM),
    ("LOGISTX", "LogistX Transport", Sector.INDUSTRIALS, "66.00", VolatilityClass.MEDIUM),
    ("AEROENG", "AeroEng Systems", Sector.INDUSTRIALS, "134.00", VolatilityClass.HIGH),
    # Infrastructure (4)
    ("BUILDONE", "BuildOne Infra", Sector.INFRA, "88.00", VolatilityClass.LOW),
    ("ROADNET", "RoadNet Highways", Sector.INFRA, "54.00", VolatilityClass.LOW),
    ("PORTCO", "PortCo Terminals", Sector.INFRA, "71.00", VolatilityClass.MEDIUM),
    ("POWERGRID", "PowerGrid Infra", Sector.INFRA, "102.00", VolatilityClass.MEDIUM),
    # Real Estate (4)
    ("HOMEBASE", "HomeBase Realty", Sector.REAL_ESTATE, "92.00", VolatilityClass.MEDIUM),
    ("URBANCO", "UrbanCo Properties", Sector.REAL_ESTATE, "68.00", VolatilityClass.HIGH),
    ("REITMAX", "REITMax Trust", Sector.REAL_ESTATE, "115.00", VolatilityClass.MEDIUM),
    ("MORTREIT", "MortgageREIT", Sector.REAL_ESTATE, "44.00", VolatilityClass.VERY_HIGH),
    # Metals (4)
    ("IRONCO", "IronCo Mining", Sector.INDUSTRIALS, "58.00", VolatilityClass.HIGH),
    ("COPPERX", "CopperX Metals", Sector.INDUSTRIALS, "82.00", VolatilityClass.HIGH),
    ("GOLDMIN", "GoldMin Resources", Sector.INDUSTRIALS, "126.00", VolatilityClass.MEDIUM),
    ("ALUMCO", "AlumCo Industries", Sector.INDUSTRIALS, "49.00", VolatilityClass.MEDIUM),
    # Consumer (4)
    ("RETAILCO", "RetailCo Markets", Sector.RETAIL, "48.00", VolatilityClass.MEDIUM),
    ("FOODCORP", "FoodCorp Industries", Sector.FOOD, "72.00", VolatilityClass.LOW),
    ("SHOPNOW", "ShopNow Retail", Sector.RETAIL, "36.00", VolatilityClass.MEDIUM),
    ("BRANDCO", "BrandCo Consumer", Sector.RETAIL, "91.00", VolatilityClass.MEDIUM),
]


def seed_tradeverse_stocks(db: Session, *, skip_existing: bool = True) -> int:
    from app.services import sector_service

    sector_service.ensure_sectors(db)
    created = 0
    for ticker, name, sector, price_s, vol in TRADEVERSE_STOCKS:
        if stock_service.get_stock_by_ticker(db, ticker) and skip_existing:
            continue
        if stock_service.get_stock_by_ticker(db, ticker):
            continue
        price = Decimal(price_s)
        stock_service.create_stock(
            db,
            StockCreate(
                ticker=ticker,
                company_name=name,
                sector=sector,
                starting_price=price,
                shares_outstanding=50_000_000,
                fair_value=price,
                volatility_class=vol,
                liquidity_class=LiquidityClass.MEDIUM,
                fundamental_profile=FundamentalProfile.CYCLICAL,
                description=f"TRADEVERSE fictional company — {name}",
            ),
        )
        created += 1
    sector_service.backfill_stock_sectors(db)
    return created
