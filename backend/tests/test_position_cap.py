"""Tests for per-stock position cap."""

from decimal import Decimal

from app.exchange.book_registry import books
from app.models import OrderSide, OrderType
from app.models.enums import Sector
from app.schemas import StockCreate, TraderCreate
from app.services import order_service, portfolio_service, stock_service, trader_service
from app.ai.runner import seed_default_agents
from app.services.liquidity_service import seed_all_liquidity


def test_buy_rejected_when_exceeding_max_position(db_session):
    books.clear()
    buyer = trader_service.create_trader(db_session, TraderCreate(name="CapBuyer"))
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="CAPTEST",
            company_name="Cap Test",
            sector=Sector.TECH,
            starting_price=Decimal("100"),
            shares_outstanding=1_000_000,
            fair_value=Decimal("100"),
        ),
    )
    seed_default_agents(db_session)
    seed_all_liquidity(db_session, quote_size=100)

    # Buy 100 shares (at cap)
    order_service.submit_order(
        db_session,
        trader_id=buyer.id,
        stock_id=stock.id,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100,
    )
    portfolio = portfolio_service.get_portfolio(db_session, buyer.id)
    assert portfolio.holdings[0].quantity == 100

    # 101st share should be rejected
    try:
        order_service.submit_order(
            db_session,
            trader_id=buyer.id,
            stock_id=stock.id,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1,
        )
        assert False, "expected OrderGatewayError"
    except order_service.OrderGatewayError as exc:
        assert exc.rejected_order is not None
        assert "max position" in (exc.rejected_order.reject_reason or "").lower()
