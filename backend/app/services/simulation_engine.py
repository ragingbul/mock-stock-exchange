"""Server-owned simulation loop — clock, events, AI ticks, broadcasts."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.engine import Connection

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.models import Stock
from app.models.enums import SimulationStatus
from app.realtime.ws_manager import manager
from app.services.event_processor import process_due_events
from app.services.market_pulse_service import run_market_pulse
from app.services.simulation_clock import advance_clock, get_or_create_state, status_dict
from app.services.simulation_settings_service import get_or_create_settings

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
_watchdog_task: asyncio.Task | None = None
_stop = asyncio.Event()
_lock_conn: Connection | None = None
AI_TICK_INTERVAL_SEC = 90.0
CLOCK_BROADCAST_INTERVAL = 5.0
MARKET_PULSE_INTERVAL_REAL = 3.0
_last_clock_broadcast = 0.0
_last_market_pulse_real = 0.0
_market_pulse_seq = 0
_last_tick_elapsed = -1.0
_last_tick_elapsed_real = 0.0
ADVISORY_LOCK_ID = 8675309


@dataclass
class TickResult:
    broadcasts: list[tuple[str, dict[str, Any]]]


def reset_market_pulse_clock(sim_elapsed: float = 0.0) -> None:
    """Force the next pulse on the following engine tick after start/reset."""
    global _last_market_pulse_real, _market_pulse_seq
    _last_market_pulse_real = 0.0
    _market_pulse_seq = 0
    _ = sim_elapsed


def _run_ai_tick(db, elapsed: float) -> list[dict]:
    from app.ai import runner as ai_runner

    state = get_or_create_state(db)
    state.last_ai_tick_elapsed_sec = elapsed
    db.commit()
    return ai_runner.run_all_agents(db)


def _ai_broadcast_messages(db, elapsed: float, results: list[dict]) -> list[tuple[str, dict[str, Any]]]:
    messages: list[tuple[str, dict[str, Any]]] = []
    traded_ids = {
        r["stock_id"] for r in results if r.get("trades", 0) > 0 and r.get("stock_id")
    }
    if traded_ids:
        for stock in db.scalars(select(Stock).where(Stock.id.in_(traded_ids))).all():
            messages.append(
                (
                    "PRICE_UPDATED",
                    {
                        "ticker": stock.ticker,
                        "ltp": str(stock.last_traded_price),
                        "stock_id": stock.id,
                    },
                )
            )
    messages.append(("LEADERBOARD_UPDATE", {"sim_elapsed_sec": elapsed}))
    messages.append(("AI_TICK", {"sim_elapsed_sec": elapsed, "actions": len(results)}))
    return messages


async def _broadcast_messages(messages: list[tuple[str, dict[str, Any]]]) -> None:
    for event, payload in messages:
        try:
            await manager.broadcast(event, payload)
        except Exception:  # noqa: BLE001
            logger.exception("Broadcast failed for event=%s", event)


def _collect_event_broadcasts(event_results: list[dict]) -> list[tuple[str, dict[str, Any]]]:
    pending: list[tuple[str, dict[str, Any]]] = []
    for er in event_results:
        etype = er.get("type")
        logger.info(
            "Timeline event executed: type=%s headline=%s",
            etype,
            er.get("headline") or er.get("checkpoint_id"),
        )
        if etype == "NEWS":
            detail = er.get("broadcast")
            if detail:
                pending.append(("NEWS_RELEASED", detail))
        elif etype == "IPO_OPEN":
            logger.info("IPO EVENT: open ticker=%s", er.get("ticker"))
            pending.append(("IPO_OPENED", er))
        elif etype == "IPO_ALLOTMENT":
            logger.info("IPO EVENT: allotment ipo_id=%s", er.get("ipo_id"))
            pending.append(("IPO_RESULT", er))
        elif etype == "IPO_LISTING":
            logger.info("IPO EVENT: listing ticker=%s", er.get("ticker"))
            pending.append(("IPO_LISTED", er))
        elif etype == "COMPANY_DISSOLUTION":
            logger.info("DISSOLUTION EVENT: %s", er)
            pending.append(("COMPANY_DISSOLVED", er))
        elif etype == "SIMULATION_END":
            with SessionLocal() as db:
                pending.append(("SIMULATION_STATUS", status_dict(db)))
    return pending


def _run_tick_sync(delta: float, now_real: float) -> TickResult | None:
    """Blocking simulation work — short DB sessions so HTTP handlers keep pool slots."""
    global _last_clock_broadcast, _last_market_pulse_real, _market_pulse_seq
    global _last_tick_elapsed, _last_tick_elapsed_real

    pending_broadcasts: list[tuple[str, dict[str, Any]]] = []

    with SessionLocal() as db:
        state = get_or_create_state(db)
        if state.status != SimulationStatus.RUNNING:
            return None
        elapsed = advance_clock(db, delta)

    _last_tick_elapsed = elapsed
    _last_tick_elapsed_real = now_real

    with SessionLocal() as db:
        event_results = process_due_events(db, elapsed)
        pending_broadcasts.extend(_collect_event_broadcasts(event_results))

    with SessionLocal() as db:
        settings = get_or_create_settings(db)
        state = get_or_create_state(db)
        app_settings = get_settings()

        if app_settings.simulation_ai_enabled and settings.simulation_ai_enabled:
            if elapsed - float(state.last_ai_tick_elapsed_sec) >= AI_TICK_INTERVAL_SEC:
                try:
                    results = _run_ai_tick(db, elapsed)
                    pending_broadcasts.extend(_ai_broadcast_messages(db, elapsed, results))
                    logger.info("AI tick at sim=%.0fs: %s actions", elapsed, len(results))
                except Exception:  # noqa: BLE001
                    logger.exception("AI tick failed — simulation continues")

        state = get_or_create_state(db)
        if elapsed >= float(state.sim_duration_sec) and state.status == SimulationStatus.RUNNING:
            state.status = SimulationStatus.COMPLETED
            session_pause(db)
            db.commit()
            logger.info("Simulation completed at sim=%.0fs", elapsed)
            pending_broadcasts.append(("SIMULATION_STATUS", status_dict(db)))
            return TickResult(broadcasts=pending_broadcasts)

    if elapsed - _last_clock_broadcast >= CLOCK_BROADCAST_INTERVAL:
        _last_clock_broadcast = elapsed
        with SessionLocal() as db:
            pending_broadcasts.append(("SIMULATION_CLOCK", status_dict(db)))

    with SessionLocal() as db:
        state = get_or_create_state(db)
        if (
            state.status == SimulationStatus.RUNNING
            and now_real - _last_market_pulse_real >= MARKET_PULSE_INTERVAL_REAL
        ):
            _last_market_pulse_real = now_real
            _market_pulse_seq += 1
            pulse_updates = run_market_pulse(
                db, float(state.sim_elapsed_sec), pulse_seq=_market_pulse_seq
            )
            if pulse_updates:
                pending_broadcasts.append(
                    ("MARKET_PULSE", {"stocks": pulse_updates, "elapsed_sec": elapsed})
                )

    return TickResult(broadcasts=pending_broadcasts)


def _acquire_advisory_lock() -> bool:
    """Return True if this process owns the simulation loop (Postgres) or SQLite dev."""
    global _lock_conn
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        logger.info("Simulation worker starting (sqlite — single process assumed)")
        return True
    try:
        _lock_conn = engine.connect()
        acquired = _lock_conn.execute(
            text(f"SELECT pg_try_advisory_lock({ADVISORY_LOCK_ID})")
        ).scalar()
        if not acquired:
            logger.error("ADVISORY LOCK NOT ACQUIRED — simulation worker will not start")
            _lock_conn.close()
            _lock_conn = None
            return False
        _lock_conn.commit()
        logger.info("ADVISORY LOCK ACQUIRED")
        return True
    except Exception:  # noqa: BLE001
        logger.error("Could not acquire simulation advisory lock — worker will not start")
        if _lock_conn is not None:
            _lock_conn.close()
            _lock_conn = None
        return False


def _release_advisory_lock() -> None:
    global _lock_conn
    if _lock_conn is None:
        return
    try:
        _lock_conn.execute(text(f"SELECT pg_advisory_unlock({ADVISORY_LOCK_ID})"))
        _lock_conn.commit()
        logger.info("Simulation advisory lock released")
    except Exception:  # noqa: BLE001
        logger.warning("Failed to release simulation advisory lock", exc_info=True)
    finally:
        _lock_conn.close()
        _lock_conn = None


async def _loop() -> None:
    while not _stop.is_set():
        if _acquire_advisory_lock():
            break
        logger.warning("Advisory lock busy — retrying in 5s")
        await asyncio.sleep(5.0)

    last_real = asyncio.get_event_loop().time()
    logger.info("Simulation engine loop started")
    try:
        while not _stop.is_set():
            await asyncio.sleep(0.25)
            now_real = asyncio.get_event_loop().time()
            delta = now_real - last_real
            last_real = now_real

            try:
                tick_result = await asyncio.to_thread(_run_tick_sync, delta, now_real)
            except Exception:  # noqa: BLE001
                logger.exception("Simulation engine tick failed")
                continue

            if tick_result is None:
                continue

            await _broadcast_messages(tick_result.broadcasts)
    finally:
        _release_advisory_lock()
        logger.info("Simulation engine loop stopped")


async def _watchdog() -> None:
    """Restart engine if sim is RUNNING but clock or task has stalled."""
    settings = get_settings()
    threshold = float(settings.simulation_stall_threshold_sec)
    while not _stop.is_set():
        await asyncio.sleep(10.0)
        if _stop.is_set():
            break
        try:
            with SessionLocal() as db:
                state = get_or_create_state(db)
                running = state.status == SimulationStatus.RUNNING
                db_elapsed = float(state.sim_elapsed_sec)

            if not running:
                continue

            if not engine_status().get("running"):
                logger.warning("Watchdog: sim RUNNING but engine task dead — restarting")
                start_engine()
                continue

            now = asyncio.get_event_loop().time()
            if _last_tick_elapsed < 0:
                continue
            stalled_real = now - _last_tick_elapsed_real
            stalled_sim = abs(db_elapsed - _last_tick_elapsed) < 0.01
            if stalled_real >= threshold and stalled_sim:
                logger.warning(
                    "Watchdog: clock stalled at %.0fs for %.0fs — restarting engine",
                    db_elapsed,
                    stalled_real,
                )
                _stop_engine_task()
                await asyncio.sleep(1.0)
                if not _stop.is_set():
                    start_engine()
        except Exception:  # noqa: BLE001
            logger.exception("Simulation watchdog check failed")


def session_pause(db) -> None:
    from app.models import MarketSession
    from app.models.enums import MarketSessionStatus

    session = db.scalar(select(MarketSession).order_by(MarketSession.id.desc()).limit(1))
    if session:
        session.status = MarketSessionStatus.CLOSED


def _stop_engine_task() -> None:
    global _task
    if _task:
        _task.cancel()
        _task = None


def start_engine() -> None:
    global _task, _watchdog_task
    if _task and not _task.done():
        return
    _stop.clear()
    _task = asyncio.create_task(_loop())
    if _watchdog_task is None or _watchdog_task.done():
        _watchdog_task = asyncio.create_task(_watchdog())
    logger.info("Simulation engine task scheduled")


def stop_engine() -> None:
    global _watchdog_task
    _stop.set()
    _stop_engine_task()
    if _watchdog_task:
        _watchdog_task.cancel()
        _watchdog_task = None
    logger.info("Simulation engine stop requested")


def engine_status() -> dict[str, Any]:
    return {"running": _task is not None and not _task.done()}
