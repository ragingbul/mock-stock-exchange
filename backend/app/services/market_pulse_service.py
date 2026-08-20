"""Gentle synchronized price ticks for chart / mark-to-market while sim is running.

Small random-walk nudges only — not a substitute for the matching engine.
News and AI still drive larger moves through real orders.
"""

from __future__ import annotations

import logging
import random
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Stock
from app.services.simulation_settings_service import get_or_create_settings
from app.services.timeline_service import phase_for_elapsed

logger = logging.getLogger(__name__)


def _quantize(price: Decimal, tick: Decimal) -> Decimal:
    if tick <= 0:
        tick = Decimal("0.05")
    steps = (price / tick).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return (steps * tick).quantize(tick)


def _phase_bias(phase: str) -> float:
    """Tiny directional drift by story phase (bps-scale per pulse)."""
    if "PHASE 1" in phase:
        return 0.00015
    if "PHASE 2" in phase:
        return -0.00005
    if "PHASE 3" in phase:
        return -0.0002
    if "PHASE 4" in phase:
        return 0.0001
    return 0.0


def run_market_pulse(db: Session, elapsed_sec: float, pulse_seq: int = 0) -> list[dict]:
    """Apply minimal up/down nudges to open stocks. Returns WS payload rows."""
    settings = get_settings()
    sim_settings = get_or_create_settings(db)
    phase = phase_for_elapsed(elapsed_sec)
    bias = _phase_bias(phase)
    seed = int(sim_settings.simulation_seed or settings.random_seed)
    rng = random.Random(seed + int(elapsed_sec * 10) + pulse_seq)

    stocks = list(
        db.scalars(
            select(Stock).where(Stock.is_open.is_(True), Stock.is_halted.is_(False))
        ).all()
    )
    updates: list[dict] = []

    for stock in stocks:
        ltp = Decimal(stock.last_traded_price)
        if ltp <= 0:
            continue
        tick = Decimal(stock.tick_size or "0.05")
        noise = rng.uniform(-0.00045, 0.00045)
        fv = Decimal(stock.fair_value or ltp)
        fv_pull = float((fv - ltp) / ltp) * 0.00005
        move = bias + noise + fv_pull
        new_px = _quantize(ltp * (Decimal("1") + Decimal(str(move))), tick)
        if new_px <= 0:
            continue
        if new_px == ltp:
            # Force a one-tick flicker so charts keep moving.
            direction = 1 if rng.random() >= 0.5 else -1
            new_px = _quantize(ltp + (tick * direction), tick)
            if new_px <= 0:
                new_px = ltp

        stock.last_traded_price = new_px
        prev = Decimal(stock.previous_close) or Decimal(stock.starting_price) or new_px
        pct = ((new_px - prev) / prev * Decimal("100")) if prev > 0 else Decimal("0")
        updates.append(
            {
                "stock_id": stock.id,
                "ticker": stock.ticker,
                "ltp": str(new_px),
                "percent_change": str(pct.quantize(Decimal("0.0001"))),
            }
        )

    if updates:
        db.commit()
    return updates
