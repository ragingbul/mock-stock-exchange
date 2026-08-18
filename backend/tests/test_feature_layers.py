"""Layer 2–9 feature tests: wallet, conditionals, IPO, news impacts, settings."""

from decimal import Decimal

from app.models.conditional_order import ConditionalStatus, ConditionalType
from app.models.enums import (
    FundamentalProfile,
    LiquidityClass,
    Sector,
    VolatilityClass,
)
from app.schemas import HoldingAdjust, StockCreate
from app.services import (
    conditional_order_service,
    ipo_service,
    news_service,
    portfolio_service,
    sector_service,
    stock_service,
)
from app.services.news_impact_resolver import combined_target_for_stock
from app.services.simulation_settings_service import get_or_create_settings, update_settings
from tests.conftest import join_participant


def _stock(db, ticker="TCO", sector=Sector.TECH, price="100"):
    sector_service.ensure_sectors(db)
    return stock_service.create_stock(
        db,
        StockCreate(
            ticker=ticker,
            company_name=f"{ticker} Inc",
            sector=sector,
            starting_price=Decimal(price),
            shares_outstanding=1_000_000,
            fair_value=Decimal(price),
            volatility_class=VolatilityClass.MEDIUM,
            liquidity_class=LiquidityClass.MEDIUM,
            fundamental_profile=FundamentalProfile.STABLE,
        ),
    )


def test_wallet_fields(client):
    client.post("/api/v1/admin/bootstrap")
    trader_id, auth = join_participant(client, "WalletUser")
    wallet = client.get(f"/api/v1/traders/{trader_id}/wallet", headers=auth).json()
    assert "available_cash" in wallet
    assert "cash_blocked_ipo" in wallet
    assert "invested" in wallet
    assert "portfolio_value" in wallet
    assert "return_pct" in wallet
    pf = client.get(f"/api/v1/traders/{trader_id}/portfolio", headers=auth).json()
    assert pf["available_cash"] == pf["cash"]
    assert "invested" in pf


def test_stop_loss_create_and_trigger(db_session):
    from app.schemas import TraderCreate
    from app.services import trader_service

    trader = trader_service.create_trader(db_session, TraderCreate(name="SLUser"))
    stock = _stock(db_session, "SLCO", price="100")
    portfolio_service.set_holding(
        db_session,
        trader.id,
        HoldingAdjust(stock_id=stock.id, quantity=100, avg_cost=Decimal("100")),
    )
    # Seed a buyer MM-like counterparty with cash by creating another trader holding nothing —
    # use liquidity via order path: give stock seller and create buy liquidity via portfolio + order.
    from app.models import OrderSide, OrderType
    from app.services import order_service

    buyer = trader_service.create_trader(db_session, TraderCreate(name="Buyer"))
    # Resting buy below so SL market sell can... actually market sell needs bids.
    order_service.submit_order(
        db_session,
        trader_id=buyer.id,
        stock_id=stock.id,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=200,
        price=Decimal("90"),
    )

    sl = conditional_order_service.create_conditional(
        db_session,
        trader_id=trader.id,
        stock_id=stock.id,
        condition_type=ConditionalType.STOP_LOSS,
        quantity=50,
        trigger_price=Decimal("92"),
    )
    assert sl.status == ConditionalStatus.ACTIVE

    # Price still above — should not trigger
    events = conditional_order_service.evaluate_conditionals_for_stock(db_session, stock.id)
    assert events == []

    stock.last_traded_price = Decimal("91")
    db_session.commit()
    events = conditional_order_service.evaluate_conditionals_for_stock(db_session, stock.id)
    assert any(e.get("event") == "STOP_LOSS_TRIGGERED" for e in events)
    db_session.refresh(sl)
    assert sl.status == ConditionalStatus.TRIGGERED


def test_take_profit_and_cancel(db_session):
    from app.schemas import TraderCreate
    from app.services import trader_service
    from app.models import OrderSide, OrderType
    from app.services import order_service

    trader = trader_service.create_trader(db_session, TraderCreate(name="TPUser"))
    stock = _stock(db_session, "TPCO", price="100")
    portfolio_service.set_holding(
        db_session,
        trader.id,
        HoldingAdjust(stock_id=stock.id, quantity=80, avg_cost=Decimal("100")),
    )
    buyer = trader_service.create_trader(db_session, TraderCreate(name="Buyer2"))
    order_service.submit_order(
        db_session,
        trader_id=buyer.id,
        stock_id=stock.id,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=200,
        price=Decimal("109"),
    )
    tp = conditional_order_service.create_conditional(
        db_session,
        trader_id=trader.id,
        stock_id=stock.id,
        condition_type=ConditionalType.TAKE_PROFIT,
        quantity=40,
        trigger_price=Decimal("108"),
    )
    cancelled = conditional_order_service.cancel_conditional(
        db_session, tp.id, trader_id=trader.id
    )
    assert cancelled.status == ConditionalStatus.CANCELLED


def test_position_close_cancels_conditionals(db_session):
    from app.schemas import TraderCreate
    from app.services import trader_service

    trader = trader_service.create_trader(db_session, TraderCreate(name="PosUser"))
    stock = _stock(db_session, "POSCO", price="100")
    portfolio_service.set_holding(
        db_session,
        trader.id,
        HoldingAdjust(stock_id=stock.id, quantity=100, avg_cost=Decimal("100")),
    )
    conditional_order_service.create_conditional(
        db_session,
        trader_id=trader.id,
        stock_id=stock.id,
        condition_type=ConditionalType.STOP_LOSS,
        quantity=100,
        trigger_price=Decimal("90"),
    )
    portfolio_service.set_holding(
        db_session,
        trader.id,
        HoldingAdjust(stock_id=stock.id, quantity=0, avg_cost=Decimal("0")),
    )
    changed = conditional_order_service.cancel_for_position_closed(
        db_session, trader.id, stock.id
    )
    assert changed
    assert all(c.status == ConditionalStatus.CANCELLED for c in changed)


def test_ipo_block_allot_partial(client):
    client.post("/api/v1/admin/bootstrap")
    sectors = client.get("/api/v1/sectors").json()
    tech = next(s for s in sectors if s["slug"] == "it")
    ipo = client.post(
        "/api/v1/admin/ipos",
        json={
            "company_name": "FutureTech Ltd",
            "ticker": "FTECH",
            "sector_id": tech["id"],
            "issue_price": "100",
            "lot_size": 50,
            "total_lots": 100,
            "winning_lots": 2,
            "maximum_lots_per_user": 2,
            "status": "draft",
        },
    ).json()
    client.post(f"/api/v1/admin/ipos/{ipo['id']}/open")
    t1_id, t1_auth = join_participant(client, "IPO1")
    t2_id, t2_auth = join_participant(client, "IPO2")
    a1 = client.post(
        f"/api/v1/ipos/{ipo['id']}/apply",
        json={"trader_id": t1_id, "requested_lots": 2},
        headers=t1_auth,
    ).json()
    assert a1["status"] == "applied"
    w1 = client.get(f"/api/v1/traders/{t1_id}/wallet", headers=t1_auth).json()
    assert float(w1["cash_blocked_ipo"]) == 100 * 50 * 2
    assert float(w1["available_cash"]) == 1_000_000 - 10_000

    client.post(
        f"/api/v1/ipos/{ipo['id']}/apply",
        json={"trader_id": t2_id, "requested_lots": 2},
        headers=t2_auth,
    )
    client.post(f"/api/v1/admin/ipos/{ipo['id']}/close")
    allot = client.post(f"/api/v1/admin/ipos/{ipo['id']}/allot").json()
    assert "allocations" in allot
    listed = client.post(f"/api/v1/admin/ipos/{ipo['id']}/list").json()
    assert listed["ticker"] == "FTECH"
    stocks = client.get("/api/v1/stocks").json()
    assert any(s["ticker"] == "FTECH" for s in stocks)


def test_news_sector_impacts_and_target(db_session):
    stock = _stock(db_session, "NBANK", Sector.FINANCE, "100")
    event = news_service.create_news(
        db_session,
        title="Bank support",
        description="Aid package",
        direction=-1,
        impact=Decimal("0.8"),
        confidence=Decimal("1"),
        market_wide=False,
        sector_impacts={"financials": -8, "technology": -2},
        stock_impacts={"nbank": -10},
        status="draft",
    )
    released = news_service.release_news(db_session, event.id)
    assert released.is_released
    detail = news_service.news_detail_dict(released)
    assert detail["sector_impacts"]["financials"] == -8
    impact = combined_target_for_stock(db_session, stock)
    # Sector-first: financials -8% with deterministic ±5% relative variation
    assert -8.5 <= impact["target_impact_pct"] <= -7.5


def test_simulation_settings_api(client):
    res = client.get("/api/v1/admin/simulation-settings")
    assert res.status_code == 200
    body = res.json()
    assert body["ai_tick_min_sec"] == 30.0
    patched = client.patch(
        "/api/v1/admin/simulation-settings",
        json={"ai_tick_min_sec": 18, "ai_tick_max_sec": 28, "news_impact_tolerance_pct": 0.75},
    ).json()
    assert patched["ai_tick_min_sec"] == 18
    assert patched["news_impact_tolerance_pct"] == 0.75


def test_conditionals_api(client):
    client.post("/api/v1/admin/bootstrap")
    trader_id, auth = join_participant(client, "CondUser")
    stocks = client.get("/api/v1/stocks").json()
    stock = stocks[0]
    # seed holdings
    client.put(
        f"/api/v1/traders/{trader_id}/holdings",
        json={"stock_id": stock["id"], "quantity": 50, "avg_cost": stock["last_traded_price"]},
    )
    ltp = float(stock["last_traded_price"])
    created = client.post(
        "/api/v1/conditionals",
        json={
            "trader_id": trader_id,
            "stock_id": stock["id"],
            "condition_type": "stop_loss",
            "quantity": 20,
            "trigger_price": str(round(ltp * 0.9, 2)),
        },
        headers=auth,
    )
    assert created.status_code == 200
    rows = client.get(f"/api/v1/traders/{trader_id}/conditionals", headers=auth).json()
    assert len(rows) >= 1
    cid = created.json()["id"]
    cancelled = client.delete(f"/api/v1/conditionals/{cid}?trader_id={trader_id}", headers=auth)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
