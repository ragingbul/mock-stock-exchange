"""Authoritative server-side simulation runtime state (singleton row)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import SimulationStatus


class SimulationState(Base):
    __tablename__ = "simulation_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[SimulationStatus] = mapped_column(
        Enum(SimulationStatus, name="simulation_status", native_enum=False),
        default=SimulationStatus.NOT_STARTED,
    )
    sim_elapsed_sec: Mapped[float] = mapped_column(Float, default=0.0)
    sim_duration_sec: Mapped[float] = mapped_column(Float, default=10800.0)
    sim_speed_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    last_ai_tick_elapsed_sec: Mapped[float] = mapped_column(Float, default=-30.0)
    clock_anchor_real: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paused_at_real: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
