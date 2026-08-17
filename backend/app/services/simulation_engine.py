"""Server-owned simulation loop — clock, events, AI ticks, broadcasts."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.database import SessionLocal
from app.models.enums import SimulationStatus
from app.realtime.ws_manager import manager
from app.services.event_processor import process_due_events
from app.services.simulation_clock import advance_clock, get_or_create_state, status_dict
from app.services.simulation_settings_service import get_or_create_settings

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
_stop = asyncio.Event()
AI_TICK_INTERVAL_SEC = 30.0
CLOCK_BROADCAST_INTERVAL = 10.0
_last_clock_broadcast = 0.0


async def _loop() -> None:
    global _last_clock_broadcast
    last_real = asyncio.get_event_loop().time()
    while not _stop.is_set():
        await asyncio.sleep(0.5)
        now_real = asyncio.get_event_loop().time()
        delta = now_real - last_real
        last_real = now_real

        try:
            with SessionLocal() as db:
                state = get_or_create_state(db)
                if state.status != SimulationStatus.RUNNING:
                    continue

                elapsed_before = float(state.sim_elapsed_sec)
                elapsed = advance_clock(db, delta)
                state = get_or_create_state(db)

                event_results = process_due_events(db, elapsed)
                for er in event_results:
                    etype = er.get("type")
                    if etype == "NEWS":
                        detail = er.get("broadcast")
                        if detail:
                            await manager.broadcast("NEWS_RELEASED", detail)
                    elif etype == "IPO_OPEN":
                        await manager.broadcast("IPO_OPENED", er)
                    elif etype == "IPO_ALLOTMENT":
                        await manager.broadcast("IPO_RESULT", er)
                    elif etype == "IPO_LISTING":
                        await manager.broadcast("IPO_LISTED", er)
                    elif etype == "COMPANY_DISSOLUTION":
                        await manager.broadcast("COMPANY_DISSOLVED", er)
                    elif etype == "SIMULATION_END":
                        await manager.broadcast("SIMULATION_STATUS", status_dict(db))

                settings = get_or_create_settings(db)
                if settings.ai_scheduler_enabled:
                    if elapsed - float(state.last_ai_tick_elapsed_sec) >= AI_TICK_INTERVAL_SEC:
                        from app.ai import runner as ai_runner

                        state.last_ai_tick_elapsed_sec = elapsed
                        db.commit()
                        try:
                            results = ai_runner.run_all_agents(db)
                            logger.info("AI tick at sim=%.0fs: %s actions", elapsed, len(results))
                            traded_ids = {
                                r["stock_id"]
                                for r in results
                                if r.get("trades", 0) > 0 and r.get("stock_id")
                            }
                            if traded_ids:
                                from sqlalchemy import select

                                from app.models import Stock

                                for stock in db.scalars(
                                    select(Stock).where(Stock.id.in_(traded_ids))
                                ).all():
                                    await manager.broadcast(
                                        "PRICE_UPDATED",
                                        {
                                            "ticker": stock.ticker,
                                            "ltp": str(stock.last_traded_price),
                                            "stock_id": stock.id,
                                        },
                                    )
                            await manager.broadcast("LEADERBOARD_UPDATE", {"sim_elapsed_sec": elapsed})
                            await manager.broadcast(
                                "AI_TICK",
                                {"sim_elapsed_sec": elapsed, "actions": len(results)},
                            )
                        except Exception:  # noqa: BLE001
                            logger.exception("AI tick failed — simulation continues")

                if elapsed >= float(state.sim_duration_sec) and state.status == SimulationStatus.RUNNING:
                    state.status = SimulationStatus.COMPLETED
                    session_pause(db)
                    db.commit()
                    await manager.broadcast("SIMULATION_STATUS", status_dict(db))

                if elapsed - _last_clock_broadcast >= CLOCK_BROADCAST_INTERVAL:
                    _last_clock_broadcast = elapsed
                    await manager.broadcast("SIMULATION_CLOCK", status_dict(db))

        except Exception:  # noqa: BLE001
            logger.exception("Simulation engine tick failed")


def session_pause(db) -> None:
    from sqlalchemy import select

    from app.models import MarketSession
    from app.models.enums import MarketSessionStatus

    session = db.scalar(select(MarketSession).order_by(MarketSession.id.desc()).limit(1))
    if session:
        session.status = MarketSessionStatus.CLOSED


def start_engine() -> None:
    global _task
    if _task and not _task.done():
        return
    _stop.clear()
    _task = asyncio.create_task(_loop())


def stop_engine() -> None:
    global _task
    _stop.set()
    if _task:
        _task.cancel()
        _task = None


def engine_status() -> dict[str, Any]:
    return {"running": _task is not None and not _task.done()}
