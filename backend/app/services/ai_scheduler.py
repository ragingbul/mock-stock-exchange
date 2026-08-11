"""Background AI tick loop with randomized 15–30s intervals."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from app.core.database import SessionLocal
from app.services.simulation_settings_service import get_or_create_settings

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
_stop = asyncio.Event()


async def _loop() -> None:
    from app.ai import runner as ai_runner
    from app.services import news_service

    rng = random.Random()
    while not _stop.is_set():
        delay = 20.0
        try:
            with SessionLocal() as db:
                settings = get_or_create_settings(db)
                if not settings.ai_scheduler_enabled:
                    delay = 5.0
                else:
                    lo = max(1.0, float(settings.ai_tick_min_sec))
                    hi = max(lo, float(settings.ai_tick_max_sec))
                    delay = rng.uniform(lo, hi)
                    # Release any due scheduled news
                    news_service.release_due_scheduled(db)
                    results = ai_runner.run_all_agents(db)
                    logger.info("AI scheduler tick: %s actions", len(results))
        except Exception:  # noqa: BLE001
            logger.exception("AI scheduler tick failed")
            delay = 10.0
        try:
            await asyncio.wait_for(_stop.wait(), timeout=delay)
        except asyncio.TimeoutError:
            continue


def start_scheduler() -> None:
    global _task
    if _task and not _task.done():
        return
    _stop.clear()
    _task = asyncio.create_task(_loop())


def stop_scheduler() -> None:
    global _task
    _stop.set()
    if _task:
        _task.cancel()
        _task = None


def scheduler_status() -> dict[str, Any]:
    return {
        "running": _task is not None and not _task.done(),
    }
