"""Market session lifecycle helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MarketSession
from app.models.enums import MarketSessionStatus


def get_active_session(db: Session) -> MarketSession | None:
    """Return the latest OPEN or PAUSED session, if any."""
    return db.scalar(
        select(MarketSession)
        .where(
            MarketSession.status.in_(
                [MarketSessionStatus.OPEN, MarketSessionStatus.PAUSED]
            )
        )
        .order_by(MarketSession.id.desc())
        .limit(1)
    )


def close_active_sessions(db: Session, *, now: datetime | None = None) -> int:
    """Close all OPEN/PAUSED sessions. Returns how many were closed."""
    now = now or datetime.now(timezone.utc)
    sessions = list(
        db.scalars(
            select(MarketSession).where(
                MarketSession.status.in_(
                    [MarketSessionStatus.OPEN, MarketSessionStatus.PAUSED]
                )
            )
        ).all()
    )
    for session in sessions:
        session.status = MarketSessionStatus.CLOSED
        session.ended_at = now
    if sessions:
        db.flush()
    return len(sessions)


def open_session(
    db: Session,
    name: str,
    *,
    now: datetime | None = None,
) -> MarketSession:
    """Close any active sessions and create a new OPEN session."""
    now = now or datetime.now(timezone.utc)
    close_active_sessions(db, now=now)
    session = MarketSession(
        name=name,
        status=MarketSessionStatus.OPEN,
        started_at=now,
    )
    db.add(session)
    db.flush()
    return session


def ensure_open_session(
    db: Session,
    name: str,
    *,
    now: datetime | None = None,
) -> tuple[MarketSession, bool]:
    """Reuse an existing OPEN session or resume PAUSED; otherwise open a new one."""
    now = now or datetime.now(timezone.utc)
    active = get_active_session(db)
    if active is not None:
        if active.status == MarketSessionStatus.PAUSED:
            active.status = MarketSessionStatus.OPEN
            db.flush()
        return active, True
    return open_session(db, name, now=now), False
