"""Layer 1 — sector catalogue, assignment, and performance summary."""

from decimal import Decimal

from app.models.enums import Sector
from app.schemas import StockCreate
from app.services import sector_service, stock_service
from app.models.enums import (
    FundamentalProfile,
    LiquidityClass,
    VolatilityClass,
)


def _make_stock(db, ticker: str, sector: Sector, price: str = "100"):
    return stock_service.create_stock(
        db,
        StockCreate(
            ticker=ticker,
            company_name=f"{ticker} Co",
            sector=sector,
            starting_price=Decimal(price),
            shares_outstanding=1_000_000,
            fair_value=Decimal(price),
            volatility_class=VolatilityClass.MEDIUM,
            liquidity_class=LiquidityClass.MEDIUM,
            fundamental_profile=FundamentalProfile.STABLE,
        ),
    )


def test_seed_default_sectors(db_session):
    created = sector_service.seed_default_sectors(db_session)
    assert created == 9
    again = sector_service.seed_default_sectors(db_session)
    assert again == 0
    sectors = sector_service.list_sectors(db_session)
    assert len(sectors) == 9
    names = {s.name for s in sectors}
    assert "Financials" in names
    assert "IT" in names
    assert "Automobiles" in names


def test_create_stock_links_sector_id(db_session):
    stock = _make_stock(db_session, "TECHONE", Sector.TECH)
    assert stock.sector_id is not None
    sector = sector_service.get_sector(db_session, stock.sector_id)
    assert sector is not None
    assert sector.slug == "it"


def test_assign_stock_sector(db_session):
    stock = _make_stock(db_session, "FINONE", Sector.FINANCE)
    finance = sector_service.get_sector_by_slug(db_session, "financials")
    energy = sector_service.get_sector_by_slug(db_session, "energy")
    assert finance and energy
    updated = sector_service.assign_stock_sector(
        db_session, stock.id, sector_id=energy.id
    )
    assert updated.sector_id == energy.id
    assert updated.sector == Sector.ENERGY


def test_sector_summary_gainers_losers(db_session):
    a = _make_stock(db_session, "UPCO", Sector.TECH, "100")
    b = _make_stock(db_session, "DOWNCO", Sector.TECH, "100")
    a.last_traded_price = Decimal("110")
    b.last_traded_price = Decimal("90")
    db_session.commit()

    tech = sector_service.get_sector_by_slug(db_session, "it")
    assert tech
    rows = sector_service.sector_summary(db_session, sector_id=tech.id)
    assert len(rows) == 1
    summary = rows[0]
    assert summary["stock_count"] == 2
    assert summary["top_gainer"]["ticker"] == "UPCO"
    assert summary["top_loser"]["ticker"] == "DOWNCO"
    # average of +10 and -10
    assert Decimal(summary["sector_change_pct"]) == Decimal("0.0000")


def test_sectors_api(client):
    client.post("/api/v1/admin/bootstrap")
    res = client.get("/api/v1/sectors")
    assert res.status_code == 200
    body = res.json()
    assert len(body) >= 9
    assert any(s["slug"] == "it" for s in body)

    tech = next(s for s in body if s["slug"] == "it")
    stocks = client.get(f"/api/v1/sectors/{tech['id']}/stocks")
    assert stocks.status_code == 200
    tickers = {s["ticker"] for s in stocks.json()}
    assert "TCS" in tickers or "HCLTECH" in tickers

    summary = client.get("/api/v1/sectors/summary")
    assert summary.status_code == 200
    assert isinstance(summary.json(), list)

    market = client.get("/api/v1/market/sectors")
    assert market.status_code == 200


def test_admin_assign_sector_api(client):
    client.post("/api/v1/admin/bootstrap")
    stocks = client.get("/api/v1/stocks").json()
    stock = stocks[0]
    sectors = client.get("/api/v1/sectors").json()
    target = next(s for s in sectors if s["slug"] == "energy")
    res = client.patch(
        f"/api/v1/admin/stocks/{stock['id']}/sector",
        json={"sector_id": target["id"]},
    )
    assert res.status_code == 200
    updated = res.json()["stock"]
    assert updated["sector_id"] == target["id"]
    assert updated["sector_slug"] == "energy"
    assert updated["sector_name"] == "Energy"


def test_list_stocks_filter_by_sector(client):
    client.post("/api/v1/admin/bootstrap")
    sectors = client.get("/api/v1/sectors").json()
    auto = next(s for s in sectors if s["slug"] == "automobiles")
    filtered = client.get(f"/api/v1/stocks?sector_id={auto['id']}")
    assert filtered.status_code == 200
    for row in filtered.json():
        assert row["sector_id"] == auto["id"]
