"""Exchange matching, order book, settlement, and gateway tests."""

from decimal import Decimal

from app.exchange.book_registry import books
from app.exchange.matching_engine import MatchingEngine
from app.exchange.order_book import OrderBook
from app.models import OrderSide, OrderType
from app.models.enums import (
    FundamentalProfile,
    LiquidityClass,
    Sector,
    VolatilityClass,
)
from app.schemas import HoldingAdjust, StockCreate, TraderCreate
from app.services import order_service, portfolio_service, stock_service, trader_service
from app.services.news_service import create_news, effective_impact, release_news
from app.services.market_model import compute_signals
from app.ai.runner import build_strategy, seed_default_agents
from app.ai.base import MarketView
from tests.conftest import join_participant


def test_price_time_priority_and_partial_fill():
    book = OrderBook(stock_id=1)
    book.add_order(side="sell", order_id=1, trader_id=2, price=Decimal("101"), quantity=100)
    book.add_order(side="sell", order_id=2, trader_id=3, price=Decimal("102"), quantity=150)
    book.add_order(side="sell", order_id=3, trader_id=4, price=Decimal("101"), quantity=50)
    # At 101, order 1 before order 3
    assert book.asks[0].order_id == 1
    assert book.asks[1].order_id == 3

    engine = MatchingEngine()
    result = engine.match(
        book,
        order_id=10,
        trader_id=1,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=150,
        limit_price=None,
    )
    assert len(result.fills) == 2
    assert result.fills[0].price == Decimal("101")
    assert result.fills[0].quantity == 100
    assert result.fills[1].price == Decimal("101")
    assert result.fills[1].quantity == 50
    assert result.remaining_quantity == 0


def test_match_buy_sell_settlement(db_session):
    books.clear()
    a = trader_service.create_trader(db_session, TraderCreate(name="A"))
    b = trader_service.create_trader(db_session, TraderCreate(name="B"))
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
    # Seed seller inventory
    portfolio_service.set_holding(
        db_session,
        b.id,
        HoldingAdjust(stock_id=stock.id, quantity=100, avg_cost=Decimal("100")),
    )

    sell, sell_trades = order_service.submit_order(
        db_session,
        trader_id=b.id,
        stock_id=stock.id,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        price=Decimal("100"),
    )
    assert sell.status.value == "open"
    assert sell_trades == []

    buy, trades = order_service.submit_order(
        db_session,
        trader_id=a.id,
        stock_id=stock.id,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=100,
        price=Decimal("100"),
    )
    assert buy.status.value == "filled"
    assert len(trades) == 1
    assert trades[0].price == Decimal("100.0000") or trades[0].price == Decimal("100")

    db_session.refresh(a)
    db_session.refresh(b)
    assert a.cash == Decimal("990000.00")
    assert b.cash == Decimal("1010000.00")
    pa = portfolio_service.get_portfolio(db_session, a.id)
    assert pa.holdings[0].quantity == 100
    stock = stock_service.get_stock(db_session, stock.id)
    assert Decimal(stock.last_traded_price) == Decimal("100.0000") or Decimal(
        stock.last_traded_price
    ) == Decimal("100")


def test_cancel_order(db_session):
    books.clear()
    a = trader_service.create_trader(db_session, TraderCreate(name="A"))
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="FINBANK",
            company_name="FinBank",
            sector=Sector.FINANCE,
            starting_price=Decimal("200"),
            shares_outstanding=1_000_000,
            fair_value=Decimal("200"),
        ),
    )
    order, _ = order_service.submit_order(
        db_session,
        trader_id=a.id,
        stock_id=stock.id,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        price=Decimal("199"),
    )
    cancelled = order_service.cancel_order(db_session, order.id, trader_id=a.id)
    assert cancelled.status.value == "cancelled"
    assert books.get(stock.id).best_bid() is None


def test_reject_insufficient_cash(db_session):
    books.clear()
    a = trader_service.create_trader(
        db_session, TraderCreate(name="Poor", starting_capital=Decimal("100"))
    )
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="X",
            company_name="X",
            sector=Sector.TECH,
            starting_price=Decimal("100"),
            shares_outstanding=1000,
            fair_value=Decimal("100"),
        ),
    )
    try:
        order_service.submit_order(
            db_session,
            trader_id=a.id,
            stock_id=stock.id,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            price=Decimal("100"),
        )
        assert False
    except order_service.OrderGatewayError as exc:
        assert "insufficient cash" in str(exc)


def test_circuit_breaker(db_session):
    books.clear()
    a = trader_service.create_trader(db_session, TraderCreate(name="A"))
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="Y",
            company_name="Y",
            sector=Sector.TECH,
            starting_price=Decimal("100"),
            shares_outstanding=1000,
            fair_value=Decimal("100"),
        ),
    )
    try:
        order_service.submit_order(
            db_session,
            trader_id=a.id,
            stock_id=stock.id,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1,
            price=Decimal("130"),  # >10% circuit
        )
        assert False
    except order_service.OrderGatewayError as exc:
        assert "circuit" in str(exc)


def test_news_decay(db_session):
    from datetime import datetime, timedelta, timezone

    event = create_news(
        db_session,
        title="Contract win",
        description="TechNova wins contract",
        affected_tickers="TECHNOVA",
        direction=1,
        impact=Decimal("0.75"),
        confidence=Decimal("0.9"),
        duration_minutes=20,
        decay_rate=Decimal("0.05"),
    )
    release_news(db_session, event.id, now=datetime.now(timezone.utc) - timedelta(minutes=10))
    db_session.refresh(event)
    impact = effective_impact(event)
    assert impact > 0
    assert impact < Decimal("0.75")


def test_market_model_does_not_set_price():
    signals = compute_signals(
        buy_notional=1000,
        sell_notional=200,
        sentiment=0.2,
        news=0.1,
        ai_pressure=0.05,
        fair_value=Decimal("100"),
        last_price=Decimal("100"),
        reference_price=Decimal("100"),
    )
    assert -1.5 <= signals.combined_force <= 1.5
    assert signals.reference_price != Decimal("0")


def test_ai_strategy_generates_order_intent():
    strategy = build_strategy("momentum", {"threshold": 0.001, "aggressiveness": 1.0, "size": 10})
    view = MarketView(
        ticker="TECHNOVA",
        stock_id=1,
        last_price=Decimal("110"),
        fair_value=Decimal("100"),
        best_bid=None,
        best_ask=None,
        recent_return=0.05,
        news_impact=0.0,
        signal=0.2,
    )
    intent = strategy.decide(view, Decimal("100000"), 0)
    assert intent is not None
    assert intent.side == "buy"


def test_seed_ai_agents(db_session):
    n = seed_default_agents(db_session)
    assert n == 7


def test_api_match_flow(client):
    books.clear()
    buyer_id, buyer_auth = join_participant(client, "Buyer")
    seller_id, seller_auth = join_participant(client, "Seller")
    stock = client.post(
        "/api/v1/stocks",
        json={
            "ticker": "TECHNOVA",
            "company_name": "TechNova",
            "sector": "tech",
            "starting_price": "100",
            "shares_outstanding": 1000000,
            "fair_value": "100",
        },
    ).json()
    client.put(
        f"/api/v1/traders/{seller_id}/holdings",
        json={"stock_id": stock["id"], "quantity": 100, "avg_cost": "100"},
    )
    client.post("/api/v1/admin/session/start")
    sell = client.post(
        "/api/v1/orders",
        json={
            "trader_id": seller_id,
            "stock_id": stock["id"],
            "side": "sell",
            "order_type": "limit",
            "quantity": 100,
            "price": "100",
        },
        headers=seller_auth,
    )
    assert sell.status_code == 201
    buy = client.post(
        "/api/v1/orders",
        json={
            "trader_id": buyer_id,
            "stock_id": stock["id"],
            "side": "buy",
            "order_type": "limit",
            "quantity": 100,
            "price": "100",
        },
        headers=buyer_auth,
    )
    assert buy.status_code == 201
    body = buy.json()
    assert body["rejected"] is False
    assert len(body["trades"]) == 1
    book = client.get(f"/api/v1/market/{stock['id']}/book")
    assert book.status_code == 200
    lb = client.get("/api/v1/leaderboard")
    assert lb.status_code == 200


def test_news_release_is_idempotent(db_session):
    from datetime import datetime, timezone

    from app.models import Stock
    from app.seed.stocks import seed_default_stocks

    seed_default_stocks(db_session)
    stock = db_session.query(Stock).filter_by(ticker="TECHNOVA").one()
    before = stock.fair_value

    event = create_news(
        db_session,
        title="Contract win",
        description="TechNova wins contract",
        affected_tickers="TECHNOVA",
        direction=1,
        impact=Decimal("0.75"),
        confidence=Decimal("0.9"),
        duration_minutes=20,
        decay_rate=Decimal("0.05"),
        fundamental_impact_pct=Decimal("5"),
    )
    release_news(db_session, event.id, now=datetime.now(timezone.utc))
    db_session.refresh(stock)
    after_first = stock.fair_value

    release_news(db_session, event.id, now=datetime.now(timezone.utc))
    db_session.refresh(stock)
    after_second = stock.fair_value

    assert after_first != before
    assert after_second == after_first


def test_book_rebuild_from_db(db_session):
    from app.models import Order, OrderStatus

    books.clear()
    trader = trader_service.create_trader(db_session, TraderCreate(name="T1"))
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="RB",
            company_name="Rebuild Co",
            sector=Sector.TECH,
            starting_price=Decimal("100"),
            shares_outstanding=1_000_000,
            fair_value=Decimal("100"),
        ),
    )
    order = Order(
        trader_id=trader.id,
        stock_id=stock.id,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=50,
        remaining_quantity=50,
        price=Decimal("105"),
        status=OrderStatus.OPEN,
    )
    db_session.add(order)
    db_session.commit()

    books.clear()
    assert books.get(stock.id).best_ask() is None

    restored = books.rebuild_from_db(db_session)
    assert restored == 1
    ask = books.get(stock.id).best_ask()
    assert ask is not None
    assert ask.order_id == order.id
    assert ask.quantity == 50


def test_get_book_unknown_stock_returns_404(client):
    res = client.get("/api/v1/market/99999/book")
    assert res.status_code == 404


def test_start_session_closes_prior_open_sessions(client):
    first = client.post("/api/v1/admin/session/start", params={"name": "A"})
    second = client.post("/api/v1/admin/session/start", params={"name": "B"})
    assert first.status_code == 200
    assert second.status_code == 200

    first_id = first.json()["id"]
    second_id = second.json()["id"]
    assert second_id > first_id

    overview = client.get("/api/v1/admin/overview").json()
    assert overview["session_id"] == second_id
    assert overview["session_status"] == "open"


def test_bootstrap_is_idempotent(client):
    books.clear()
    first = client.post("/api/v1/admin/bootstrap")
    second = client.post("/api/v1/admin/bootstrap")
    assert first.status_code == 200
    assert second.status_code == 200

    first_body = first.json()
    second_body = second.json()
    assert first_body["stocks_created"] > 0
    assert first_body["agents_created"] > 0
    assert first_body["liquidity_quotes"] > 0

    assert second_body["stocks_created"] == 0
    assert second_body["agents_created"] == 0
    assert second_body["already_bootstrapped"] is True
    assert second_body["session_reused"] is True
    assert second_body["session_id"] == first_body["session_id"]
    assert second_body["liquidity_quotes"] == 0


def test_bootstrap_resumes_paused_session(client):
    books.clear()
    boot = client.post("/api/v1/admin/bootstrap").json()
    client.post("/api/v1/admin/session/pause")
    resumed = client.post("/api/v1/admin/bootstrap").json()

    assert resumed["already_bootstrapped"] is True
    assert resumed["session_reused"] is True
    assert resumed["session_id"] == boot["session_id"]

    overview = client.get("/api/v1/admin/overview").json()
    assert overview["session_status"] == "open"
