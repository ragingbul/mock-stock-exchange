"""Runtime simulation settings (admin-configurable)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SimulationSettings(Base):
    __tablename__ = "simulation_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ai_tick_min_sec: Mapped[float] = mapped_column(Float, default=30.0)
    ai_tick_max_sec: Mapped[float] = mapped_column(Float, default=30.0)
    ai_scheduler_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    simulation_ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    news_impact_tolerance_pct: Mapped[float] = mapped_column(Float, default=0.5)
    max_price_move_per_tick_pct: Mapped[float] = mapped_column(Float, default=3.0)
    max_daily_move_pct: Mapped[float] = mapped_column(Float, default=15.0)
    market_maker_aggressiveness: Mapped[float] = mapped_column(Float, default=1.0)
    ai_aggressiveness: Mapped[float] = mapped_column(Float, default=1.0)
    news_reaction_strength: Mapped[float] = mapped_column(Float, default=1.0)
    ipo_allocation_method: Mapped[str] = mapped_column(String(32), default="random")
    max_ipo_lots_per_user: Mapped[int] = mapped_column(Integer, default=2)
    news_combined_impact_cap_pct: Mapped[float] = mapped_column(Float, default=15.0)
    sim_duration_sec: Mapped[float] = mapped_column(Float, default=10800.0)
    sim_speed_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    simulation_seed: Mapped[int] = mapped_column(Integer, default=42)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
