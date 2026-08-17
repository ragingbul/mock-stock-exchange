"""Phase 1 — traders, stocks, holdings, portfolio valuation."""

from decimal import Decimal

from app.schemas import HoldingAdjust, StockCreate, TraderCreate
from app.seed.stocks import seed_default_stocks
from app.services import portfolio_service, stock_service, trader_service
from tests.conftest import join_participant
from app.models.enums import (
    FundamentalProfile,
    LiquidityClass,
    Sector,
    VolatilityClass,
)


def test_create_two_traders_and_one_stock(db_session) -> None:
    a = trader_service.create_trader(db_session, TraderCreate(name="Trader A"))
    b = trader_service.create_trader(db_session, TraderCreate(name="Trader B"))
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="TECHNOVA",
            company_name="TechNova Systems",
            sector=Sector.TECH,
            starting_price=Decimal("100"),
            shares_outstanding=50_000_000,
            fair_value=Decimal("105"),
            volatility_class=VolatilityClass.HIGH,
            liquidity_class=LiquidityClass.HIGH,
            fundamental_profile=FundamentalProfile.GROWTH,
        ),
    )

    assert a.id != b.id
    assert a.cash == Decimal("1000000.00")
    assert b.cash == Decimal("1000000.00")
    assert stock.ticker == "TECHNOVA"
    assert stock.last_traded_price == Decimal("100")
    assert stock.fair_value == Decimal("105")


def test_cash_and_holdings_tracked(db_session) -> None:
    trader = trader_service.create_trader(db_session, TraderCreate(name="Alice"))
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="FINBANK",
            company_name="FinBank Holdings",
            sector=Sector.FINANCE,
            starting_price=Decimal("200"),
            shares_outstanding=10_000_000,
            fair_value=Decimal("210"),
        ),
    )

    portfolio_service.set_holding(
        db_session,
        trader.id,
        HoldingAdjust(stock_id=stock.id, quantity=100, avg_cost=Decimal("200")),
    )

    portfolio = portfolio_service.get_portfolio(db_session, trader.id)
    assert portfolio.cash == Decimal("1000000.00")
    assert len(portfolio.holdings) == 1
    assert portfolio.holdings[0].quantity == 100
    assert portfolio.holdings_value == Decimal("20000")
    assert portfolio.portfolio_value == Decimal("1020000.00")
    assert portfolio.unrealized_pnl == Decimal("0")


def test_unrealized_pnl_uses_last_traded_price(db_session) -> None:
    trader = trader_service.create_trader(db_session, TraderCreate(name="Bob"))
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="AUTOMAX",
            company_name="AutoMax",
            sector=Sector.AUTO,
            starting_price=Decimal("100"),
            shares_outstanding=1_000_000,
            fair_value=Decimal("100"),
        ),
    )
    # Mark price moved without touching cash (LTP later comes from trades).
    stock.last_traded_price = Decimal("110")
    db_session.commit()

    portfolio_service.set_holding(
        db_session,
        trader.id,
        HoldingAdjust(stock_id=stock.id, quantity=50, avg_cost=Decimal("100")),
    )
    portfolio = portfolio_service.get_portfolio(db_session, trader.id)
    assert portfolio.holdings_value == Decimal("5500")
    assert portfolio.unrealized_pnl == Decimal("500")
    assert portfolio.total_pnl == Decimal("500")


def test_reject_duplicate_ticker(db_session) -> None:
    payload = StockCreate(
        ticker="FOODCORP",
        company_name="FoodCorp",
        sector=Sector.FOOD,
        starting_price=Decimal("70"),
        shares_outstanding=1_000_000,
        fair_value=Decimal("72"),
    )
    stock_service.create_stock(db_session, payload)
    try:
        stock_service.create_stock(db_session, payload)
        assert False, "expected duplicate ticker error"
    except stock_service.StockServiceError:
        pass


def test_seed_default_stocks(db_session) -> None:
    created = seed_default_stocks(db_session)
    assert created == 10
    assert len(stock_service.list_stocks(db_session)) == 10
    # Idempotent
    assert seed_default_stocks(db_session) == 0


def test_api_create_traders_and_portfolio(client) -> None:
    trader_id, auth = join_participant(client, "Trader A")
    join_participant(client, "Trader B")

    stock = client.post(
        "/api/v1/stocks",
        json={
            "ticker": "TECHNOVA",
            "company_name": "TechNova Systems",
            "sector": "tech",
            "starting_price": "100.00",
            "shares_outstanding": 50_000_000,
            "fair_value": "105.00",
        },
    )
    assert stock.status_code == 201
    stock_id = stock.json()["id"]

    holding = client.put(
        f"/api/v1/traders/{trader_id}/holdings",
        json={"stock_id": stock_id, "quantity": 10, "avg_cost": "100"},
    )
    assert holding.status_code == 200
    assert holding.json()["quantity"] == 10

    portfolio = client.get(f"/api/v1/traders/{trader_id}/portfolio", headers=auth)
    assert portfolio.status_code == 200
    body = portfolio.json()
    assert body["holdings_value"] == "1000.0000" or Decimal(body["holdings_value"]) == Decimal(
        "1000"
    )
    assert Decimal(body["portfolio_value"]) == Decimal("1001000.00")


def test_api_seed_stocks(client) -> None:
    response = client.post("/api/v1/stocks/seed/defaults")
    assert response.status_code == 201
    assert response.json()["created"] == 10
    listed = client.get("/api/v1/stocks")
    assert listed.status_code == 200
    assert len(listed.json()) == 10
