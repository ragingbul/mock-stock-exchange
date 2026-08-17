"""Admin simulation settings singleton."""

from __future__ import annotations

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


def settings_dict(row: SimulationSettings) -> dict:
    return {
        "ai_tick_min_sec": row.ai_tick_min_sec,
        "ai_tick_max_sec": row.ai_tick_max_sec,
        "ai_scheduler_enabled": row.ai_scheduler_enabled,
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
