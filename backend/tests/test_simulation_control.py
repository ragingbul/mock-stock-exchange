"""Tests for TRADEVERSE simulation clock, timeline, and START/STOP/RESET."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import SimulationState, TimelineEvent, Trader
from app.models.enums import SimulationStatus, TimelineEventStatus
from app.services.simulation_controller import (
    SimulationControlError,
    reset_simulation,
    start_simulation,
    stop_simulation,
)
from app.services.timeline_service import load_timeline_json, parse_time_to_sec, validate_timeline


def test_timeline_json_valid():
    errors = validate_timeline()
    assert errors == [], errors


def test_timeline_duration_end():
    data = load_timeline_json()
    end_events = [e for e in data["events"] if e["type"] == "SIMULATION_END"]
    assert len(end_events) == 1
    assert parse_time_to_sec(end_events[0]["time"]) == 10800


def test_parse_time_hh_mm_not_mm_ss():
    assert parse_time_to_sec("00:03") == 180
    assert parse_time_to_sec("01:55") == 6900
    assert parse_time_to_sec("02:59:30") == 10770


def test_start_stop_resume(db_session):
    from app.services.timeline_service import seed_timeline_from_json

    seed_timeline_from_json(db_session, force=True)
    reset_simulation(db_session)
    result = start_simulation(db_session)
    assert result["status"] == "running"
    state = db_session.scalar(select(SimulationState).limit(1))
    assert state.status == SimulationStatus.RUNNING
    elapsed_at_pause = float(state.sim_elapsed_sec)

    stop = stop_simulation(db_session)
    assert stop["status"] == "paused"

    resume = start_simulation(db_session)
    assert resume["status"] == "running"
    state2 = db_session.scalar(select(SimulationState).limit(1))
    assert float(state2.sim_elapsed_sec) == elapsed_at_pause


def test_reset_restores_timeline_pending(db_session):
    from app.services.timeline_service import seed_timeline_from_json

    seed_timeline_from_json(db_session, force=True)
    reset_simulation(db_session)
    state = db_session.scalar(select(SimulationState).limit(1))
    assert state.status == SimulationStatus.NOT_STARTED
    assert float(state.sim_elapsed_sec) == 0.0


def test_trading_blocked_when_paused(db_session):
    from app.models import MarketSession, Stock
    from app.models.enums import MarketSessionStatus
    from app.models.order_enums import OrderSide, OrderType
    from app.schemas import StockCreate, TraderCreate
    from app.services.order_service import OrderGatewayError, submit_order
    from app.services import stock_service, trader_service
    from app.models.enums import Sector, VolatilityClass, LiquidityClass, FundamentalProfile, TraderType

    reset_simulation(db_session)
    db_session.add(MarketSession(name="test", status=MarketSessionStatus.OPEN))
    trader = trader_service.create_trader(
        db_session, TraderCreate(name="T1", trader_type=TraderType.HUMAN)
    )
    stock = stock_service.create_stock(
        db_session,
        StockCreate(
            ticker="TESTCO",
            company_name="Test Co",
            sector=Sector.TECH,
            starting_price=100,
            shares_outstanding=1_000_000,
            fair_value=100,
            volatility_class=VolatilityClass.MEDIUM,
            liquidity_class=LiquidityClass.MEDIUM,
            fundamental_profile=FundamentalProfile.CYCLICAL,
        ),
    )
    db_session.commit()
    start_simulation(db_session)
    stop_simulation(db_session)

    with pytest.raises(OrderGatewayError, match="simulation is paused"):
        submit_order(
            db_session,
            trader_id=trader.id,
            stock_id=stock.id,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1,
        )


def test_start_rejects_invalid_timeline(db_session, monkeypatch):
    reset_simulation(db_session)
    monkeypatch.setattr(
        "app.services.simulation_controller.validate_timeline",
        lambda: ["forced validation error"],
    )
    with pytest.raises(SimulationControlError, match="Timeline validation failed"):
        start_simulation(db_session)
