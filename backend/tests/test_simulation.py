"""Simulation load-ish consistency test (Phase 14)."""

from decimal import Decimal

from app.exchange.book_registry import books
from app.models import OrderSide, OrderType
from app.schemas import HoldingAdjust, TraderCreate
from app.seed.stocks import seed_default_stocks
from app.services import order_service, portfolio_service, stock_service, trader_service
from app.ai.runner import seed_default_agents


def test_simulation_many_orders(db_session):
    books.clear()
    assert seed_default_stocks(db_session) == 10
    traders = [
        trader_service.create_trader(db_session, TraderCreate(name=f"T{i}"))
        for i in range(20)
    ]
    assert seed_default_agents(db_session) == 7
    stocks = stock_service.list_stocks(db_session)

    # Give every other trader inventory to sell
    for i, trader in enumerate(traders):
        if i % 2 == 1:
            for stock in stocks[:3]:
                portfolio_service.set_holding(
                    db_session,
                    trader.id,
                    HoldingAdjust(
                        stock_id=stock.id, quantity=500, avg_cost=stock.starting_price
                    ),
                )

    orders = 0
    for i in range(200):
        stock = stocks[i % len(stocks)]
        buyer = traders[i % len(traders)]
        seller = traders[(i + 1) % len(traders)]
        px = Decimal(stock.last_traded_price)
        try:
            order_service.submit_order(
                db_session,
                trader_id=seller.id,
                stock_id=stock.id,
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=5,
                price=px,
            )
            orders += 1
        except order_service.OrderGatewayError:
            pass
        try:
            order_service.submit_order(
                db_session,
                trader_id=buyer.id,
                stock_id=stock.id,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=5,
                price=px,
            )
            orders += 1
        except order_service.OrderGatewayError:
            pass

    assert orders > 50
    # Accounting invariant: total cash across traders finite and non-negative
    for t in traders:
        db_session.refresh(t)
        assert t.cash >= 0
        port = portfolio_service.get_portfolio(db_session, t.id)
        assert port.portfolio_value >= 0
