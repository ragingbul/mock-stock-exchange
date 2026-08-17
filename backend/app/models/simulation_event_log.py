"""Internal simulation audit log (admin/debug only)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SimulationEventLog(Base):
    __tablename__ = "simulation_event_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sim_elapsed_sec: Mapped[float] = mapped_column(Float, index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
