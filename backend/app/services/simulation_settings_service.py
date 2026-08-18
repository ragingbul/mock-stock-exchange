"""Admin simulation settings singleton."""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.simulation_settings import SimulationSettings


def get_or_create_settings(db: Session) -> SimulationSettings:
    row = db.scalar(select(SimulationSettings).order_by(SimulationSettings.id).limit(1))
    if row is None:
        row = SimulationSettings()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def update_settings(db: Session, **kwargs) -> SimulationSettings:
    row = get_or_create_settings(db)
    for key, value in kwargs.items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def apply_simulation_speed_override_if_set(db: Session) -> bool:
    """Apply SIMULATION_SPEED env only when explicitly set in the environment."""
    if "SIMULATION_SPEED" not in os.environ:
        return False
    from app.core.config import get_settings

    settings = get_settings()
    update_settings(db, sim_speed_multiplier=float(settings.simulation_speed))
    return True


def sync_runtime_speed_from_settings(db: Session) -> float:
    """Copy persisted settings speed into simulation_state after optional env override."""
    from app.services.simulation_clock import get_or_create_state

    apply_simulation_speed_override_if_set(db)
    sim_settings = get_or_create_settings(db)
    state = get_or_create_state(db)
    state.sim_speed_multiplier = float(sim_settings.sim_speed_multiplier or 1.0)
    state.sim_duration_sec = float(sim_settings.sim_duration_sec or 10800)
    db.commit()
    return float(state.sim_speed_multiplier)


def sync_speed_from_config(db: Session) -> SimulationSettings:
    """Deprecated alias — use apply_simulation_speed_override_if_set."""
    apply_simulation_speed_override_if_set(db)
    return get_or_create_settings(db)


def settings_dict(row: SimulationSettings) -> dict:
    return {
        "ai_tick_min_sec": row.ai_tick_min_sec,
        "ai_tick_max_sec": row.ai_tick_max_sec,
        "ai_scheduler_enabled": row.ai_scheduler_enabled,
        "simulation_ai_enabled": row.simulation_ai_enabled,
        "news_impact_tolerance_pct": row.news_impact_tolerance_pct,
        "max_price_move_per_tick_pct": row.max_price_move_per_tick_pct,
        "max_daily_move_pct": row.max_daily_move_pct,
        "market_maker_aggressiveness": row.market_maker_aggressiveness,
        "ai_aggressiveness": row.ai_aggressiveness,
        "news_reaction_strength": row.news_reaction_strength,
        "ipo_allocation_method": row.ipo_allocation_method,
        "max_ipo_lots_per_user": row.max_ipo_lots_per_user,
        "news_combined_impact_cap_pct": row.news_combined_impact_cap_pct,
        "sim_duration_sec": row.sim_duration_sec,
        "sim_speed_multiplier": row.sim_speed_multiplier,
        "simulation_seed": row.simulation_seed,
    }
