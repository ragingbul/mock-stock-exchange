"""Tests for immediate participant market orders."""

from decimal import Decimal

from app.exchange.book_registry import books
from app.models import OrderSide, OrderType
from app.models.enums import Sector
from app.schemas import StockCreate, TraderCreate
from app.services import order_service, portfolio_service, stock_service, trader_service
from app.ai.runner import seed_default_agents
from tests.conftest import join_participant
from app.services.liquidity_service import seed_all_liquidity
from app.services.execution_summary import build_execution_summary


def test_market_buy_executes_with_seeded_liquidity(db_session):
    books.clear()
    buyer = trader_service.create_trader(db_session, TraderCreate(name="Buyer"))
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="TECHNOVA",
            company_name="TechNova",
            sector=Sector.TECH,
            starting_price=Decimal("100"),
            shares_outstanding=1_000_000,
            fair_value=Decimal("100"),
        ),
    )
    seed_default_agents(db_session)
    seed_all_liquidity(db_session, quote_size=100)

    order, trades = order_service.submit_order(
        db_session,
        trader_id=buyer.id,
        stock_id=stock.id,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
    )
    assert order.status.value in {"filled", "partially_filled"}
    assert len(trades) >= 1
    summary = build_execution_summary(order, trades, stock)
    assert summary["executed"] is True
    assert summary["filled_quantity"] == 10

    portfolio = portfolio_service.get_portfolio(db_session, buyer.id)
    assert portfolio.holdings[0].quantity == 10
    assert portfolio.cash < Decimal("1000000")


def test_market_buy_provisions_liquidity_on_empty_book(db_session):
    books.clear()
    buyer = trader_service.create_trader(db_session, TraderCreate(name="Buyer2"))
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="AUTOMAX",
            company_name="AutoMax",
            sector=Sector.AUTO,
            starting_price=Decimal("85"),
            shares_outstanding=1_000_000,
            fair_value=Decimal("85"),
        ),
    )
    seed_default_agents(db_session)
    # No seed_all_liquidity — provision should happen on market order path

    order, trades = order_service.submit_order(
        db_session,
        trader_id=buyer.id,
        stock_id=stock.id,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=5,
    )
    assert len(trades) >= 1
    assert order.status.value in {"filled", "partially_filled"}


def test_market_order_api_returns_execution_summary(client):
    books.clear()
    trader_id, auth = join_participant(client, "API Buyer")
    client.post("/api/v1/stocks/seed/defaults")
    client.post("/api/v1/admin/bootstrap")
    stocks = client.get("/api/v1/stocks").json()
    stock_id = stocks[0]["id"]

    res = client.post(
        "/api/v1/orders",
        json={
            "trader_id": trader_id,
            "stock_id": stock_id,
            "side": "buy",
            "order_type": "market",
            "quantity": 3,
        },
        headers=auth,
    )
    assert res.status_code == 201
    body = res.json()
    assert "execution_summary" in body
    assert body["execution_summary"]["ticker"] == stocks[0]["ticker"]
    if body["executed"]:
        assert body["execution_summary"]["filled_quantity"] == 3

    portfolio = client.get(f"/api/v1/traders/{trader_id}/portfolio", headers=auth).json()
    assert Decimal(portfolio["cash"]) < Decimal("1000000")
