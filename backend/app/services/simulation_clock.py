"""Simulation clock — single source of elapsed simulation time."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import SimulationStatus
from app.models.simulation_state import SimulationState
from app.services.simulation_settings_service import get_or_create_settings
from app.services.timeline_service import SIM_DURATION_SEC, format_sim_time, phase_for_elapsed


def get_or_create_state(db: Session) -> SimulationState:
    row = db.scalar(select(SimulationState).order_by(SimulationState.id).limit(1))
    if row is None:
        settings = get_or_create_settings(db)
        row = SimulationState(
            status=SimulationStatus.NOT_STARTED,
            sim_duration_sec=float(settings.sim_duration_sec or SIM_DURATION_SEC),
            sim_speed_multiplier=float(settings.sim_speed_multiplier or 1.0),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def is_trading_enabled(state: SimulationState) -> bool:
    return state.status == SimulationStatus.RUNNING


def advance_clock(db: Session, real_delta_sec: float) -> float:
    """Advance elapsed time when RUNNING. Returns new elapsed seconds."""
    state = get_or_create_state(db)
    if state.status != SimulationStatus.RUNNING:
        return float(state.sim_elapsed_sec)
    speed = float(state.sim_speed_multiplier or 1.0)
    state.sim_elapsed_sec = min(
        float(state.sim_duration_sec),
        float(state.sim_elapsed_sec) + real_delta_sec * speed,
    )
    state.updated_at = datetime.now(timezone.utc)
    db.commit()
    return float(state.sim_elapsed_sec)


def status_dict(db: Session) -> dict:
    state = get_or_create_state(db)
    elapsed = float(state.sim_elapsed_sec)
    return {
        "status": state.status.value,
        "elapsed_sec": elapsed,
        "elapsed": format_sim_time(elapsed),
        "duration_sec": float(state.sim_duration_sec),
        "duration": format_sim_time(state.sim_duration_sec),
        "current_phase": phase_for_elapsed(elapsed),
        "sim_speed_multiplier": float(state.sim_speed_multiplier),
        "trading_enabled": is_trading_enabled(state),
    }
