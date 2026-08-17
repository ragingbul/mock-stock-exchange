"""Preloaded timeline events — single source of truth for scheduled simulation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import TimelineEventStatus, TimelineEventType


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    checkpoint_id: Mapped[int] = mapped_column(Integer, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sim_offset_sec: Mapped[float] = mapped_column(Float, index=True)
    phase: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[TimelineEventType] = mapped_column(
        Enum(TimelineEventType, name="timeline_event_type", native_enum=False)
    )
    headline: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[TimelineEventStatus] = mapped_column(
        Enum(TimelineEventStatus, name="timeline_event_status", native_enum=False),
        default=TimelineEventStatus.PENDING,
        index=True,
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
