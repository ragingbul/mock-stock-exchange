"""Company dissolution behaviour."""

from decimal import Decimal

import pytest

from app.models import OrderSide, OrderType
from app.models.enums import Sector, StockStatus
from app.schemas import StockCreate, TraderCreate
from app.services import order_service, stock_service, trader_service
from app.services.dissolution_service import dissolve_company
from app.services.order_service import OrderGatewayError


def test_dissolution_blocks_trading_and_runs_once(db_session):
    trader = trader_service.create_trader(db_session, TraderCreate(name="DissolveUser"))
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="DISSOLVECO",
            company_name="Dissolve Co",
            sector=Sector.TECH,
            starting_price=Decimal("100"),
            shares_outstanding=1_000_000,
            fair_value=Decimal("100"),
        ),
    )
    first = dissolve_company(db_session, ticker="DISSOLVECO", liquidation_price="50")
    assert first["ticker"] == "DISSOLVECO"
    db_session.refresh(stock)
    assert stock.is_open is False
    assert stock.status == StockStatus.DISSOLVED.value

    second = dissolve_company(db_session, ticker="DISSOLVECO", liquidation_price="50")
    assert second.get("already_dissolved") is True

    with pytest.raises(OrderGatewayError):
        order_service.submit_order(
            db_session,
            trader_id=trader.id,
            stock_id=stock.id,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1,
        )
