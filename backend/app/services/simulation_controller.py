"""START / STOP / RESET orchestration for TRADEVERSE simulation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ai import runner as ai_runner
from app.core.config import get_settings
from app.exchange.book_registry import books
from app.models import (
    ConditionalOrder,
    Holding,
    IPO,
    IPOApplication,
    MarketSession,
    NewsEvent,
    NewsStockImpact,
    Order,
    SimulationEventLog,
    SimulationState,
    Stock,
    TimelineEvent,
    Trade,
    Trader,
)
from app.models.enums import MarketSessionStatus, SimulationStatus, StockStatus, TimelineEventStatus
from app.models.order_enums import OrderStatus
from app.services import order_book_service, sector_service
from app.services.liquidity_service import seed_all_liquidity
from app.services.simulation_clock import get_or_create_state, status_dict
from app.services.simulation_settings_service import get_or_create_settings
from app.services.timeline_service import seed_timeline_from_json, validate_timeline

logger = logging.getLogger(__name__)


class SimulationControlError(Exception):
    pass


def bootstrap_universe(db: Session) -> dict:
    """Seed sectors, stocks, timeline, AI agents, liquidity if empty.

    Use Admin RESET (not legacy /admin/bootstrap) for the full 40-stock TRADEVERSE universe.
    """
    from app.seed.tradeverse_stocks import TRADEVERSE_STOCKS, canonical_tradable_count, seed_tradeverse_stocks

    sectors_created = sector_service.seed_tradeverse_sectors(db)
    stocks_created = seed_tradeverse_stocks(db)
    removed = _remove_non_canonical_stocks(db)
    linked = sector_service.backfill_stock_sectors(db)
    expected = canonical_tradable_count()
    canonical_count = _count_canonical_stocks(db)
    if canonical_count != expected:
        raise SimulationControlError(
            f"TRADEVERSE universe incomplete: expected {expected} tradable stocks, found {canonical_count}"
        )
    timeline_created = seed_timeline_from_json(db)
    agents = ai_runner.seed_default_agents(db)
    ai_runner.sync_intensity_configs(db)
    liquidity = seed_all_liquidity(db)
    db.commit()
    return {
        "message": "Canonical stock universe loaded successfully",
        "tradable_stocks": canonical_count,
        "expected_tradable": expected,
        "sectors_created": sectors_created,
        "stocks_created": stocks_created,
        "stocks_removed": removed,
        "stocks_linked": linked,
        "canonical_stocks": canonical_count,
        "timeline_events": timeline_created,
        "agents_created": agents,
        "liquidity_quotes": liquidity,
    }


def _canonical_tickers() -> set[str]:
    from app.seed.tradeverse_stocks import TRADEVERSE_STOCKS

    return {ticker for ticker, *_ in TRADEVERSE_STOCKS}


def _count_canonical_stocks(db: Session) -> int:
    tickers = _canonical_tickers()
    return int(
        db.scalar(select(func.count(Stock.id)).where(Stock.ticker.in_(tickers))) or 0
    )


def _remove_non_canonical_stocks(db: Session) -> int:
    """Remove legacy/default stocks not in the TRADEVERSE catalogue."""
    tickers = _canonical_tickers()
    orphans = list(
        db.scalars(select(Stock).where(Stock.ticker.notin_(tickers))).all()
    )
    for stock in orphans:
        db.delete(stock)
    if orphans:
        db.flush()
    return len(orphans)


def start_simulation(db: Session) -> dict:
    state = get_or_create_state(db)
    if state.status == SimulationStatus.COMPLETED:
        raise SimulationControlError("simulation already completed — press RESET first")
    if state.status == SimulationStatus.RUNNING:
        return {"ok": True, "message": "already running", **status_dict(db)}

    errors = validate_timeline()
    if errors:
        raise SimulationControlError("Timeline validation failed: " + "; ".join(errors))

    # Ensure universe exists
    stock_count = db.scalar(select(func.count(Stock.id))) or 0
    if stock_count == 0:
        bootstrap_universe(db)

    timeline_count = db.scalar(select(func.count(TimelineEvent.id))) or 0
    if timeline_count == 0:
        seed_timeline_from_json(db)

    settings = get_or_create_settings(db)
    state.sim_duration_sec = float(settings.sim_duration_sec or 10800)
    from app.services.simulation_settings_service import sync_runtime_speed_from_settings

    sync_runtime_speed_from_settings(db)

    if state.status == SimulationStatus.NOT_STARTED:
        state.sim_elapsed_sec = 0.0
        state.last_ai_tick_elapsed_sec = -30.0
        from app.services.simulation_engine import reset_market_pulse_clock

        reset_market_pulse_clock(0.0)

    state.status = SimulationStatus.RUNNING
    state.clock_anchor_real = datetime.now(timezone.utc)
    state.paused_at_real = None

    session = db.scalar(select(MarketSession).order_by(MarketSession.id.desc()).limit(1))
    if session is None:
        session = MarketSession(
            name="TRADEVERSE Live",
            status=MarketSessionStatus.OPEN,
            started_at=datetime.now(timezone.utc),
        )
        db.add(session)
    else:
        session.status = MarketSessionStatus.OPEN

    order_book_service.rebuild_books_from_db(db)
    db.commit()
    logger.info("Simulation started")
    return {"ok": True, "action": "start", **status_dict(db)}


def stop_simulation(db: Session) -> dict:
    state = get_or_create_state(db)
    if state.status != SimulationStatus.RUNNING:
        raise SimulationControlError(f"cannot stop from status {state.status.value}")

    state.status = SimulationStatus.PAUSED
    state.paused_at_real = datetime.now(timezone.utc)

    session = db.scalar(select(MarketSession).order_by(MarketSession.id.desc()).limit(1))
    if session:
        session.status = MarketSessionStatus.PAUSED

    db.commit()
    logger.info("Simulation stopped at elapsed=%.0fs", float(state.sim_elapsed_sec))
    return {"ok": True, "action": "stop", **status_dict(db)}


def reset_simulation(db: Session) -> dict:
    """Atomic-ish full reset to deterministic initial state."""
    settings = get_settings()
    try:
        books.clear()
        db.execute(delete(Trade))
        db.execute(delete(Order))
        db.execute(delete(ConditionalOrder))
        db.execute(delete(Holding))
        db.execute(delete(IPOApplication))
        db.execute(delete(IPO))
        db.execute(delete(NewsStockImpact))
        db.execute(delete(NewsEvent))
        db.execute(delete(SimulationEventLog))
        db.execute(delete(TimelineEvent))

        # Reset stocks
        for stock in db.scalars(select(Stock)).all():
            stock.last_traded_price = stock.starting_price
            stock.previous_close = stock.starting_price
            stock.fair_value = stock.starting_price
            stock.is_open = True
            stock.is_halted = False
            stock.status = StockStatus.ACTIVE.value
            stock.liquidation_price = None

        # Reset human + AI traders
        cap = Decimal(str(settings.default_starting_capital))
        for trader in db.scalars(select(Trader)).all():
            trader.cash = cap if trader.trader_type.value == "human" else trader.starting_capital
            trader.cash_blocked_ipo = Decimal("0")
            trader.realized_pnl = Decimal("0")
            trader.is_active = True

        db.execute(delete(MarketSession))

        state = get_or_create_state(db)
        state.status = SimulationStatus.NOT_STARTED
        state.sim_elapsed_sec = 0.0
        state.last_ai_tick_elapsed_sec = -30.0
        state.clock_anchor_real = None
        state.paused_at_real = None

        sim_settings = get_or_create_settings(db)
        sim_settings.simulation_ai_enabled = get_settings().simulation_ai_enabled
        state.sim_duration_sec = float(sim_settings.sim_duration_sec or 10800)

        from app.services.simulation_settings_service import sync_runtime_speed_from_settings
        from app.services.simulation_engine import reset_market_pulse_clock

        sync_runtime_speed_from_settings(db)
        reset_market_pulse_clock(0.0)

        seed_timeline_from_json(db, force=True)
        bootstrap = bootstrap_universe(db)

        db.commit()
        logger.info("Simulation reset completed")
        return {
            "ok": True,
            "action": "reset",
            "message": bootstrap["message"],
            "tradable_stocks": bootstrap["tradable_stocks"],
            "expected_tradable": bootstrap["expected_tradable"],
            **status_dict(db),
        }
    except Exception:
        db.rollback()
        logger.exception("Reset failed")
        raise SimulationControlError("reset failed — database rolled back") from None
