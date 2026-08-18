"""Load, validate, and seed the preloaded TRADEVERSE timeline JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.enums import TimelineEventStatus, TimelineEventType
from app.models.timeline_event import TimelineEvent

TIMELINE_PATH = Path(__file__).resolve().parents[1] / "seed" / "tradeverse_timeline.json"
SIM_DURATION_SEC = 10800.0

PHASES = [
    (0, 2400, "PHASE 1 — EUPHORIA"),
    (2400, 4800, "PHASE 2 — CRACKS / DENIAL"),
    (4800, 9600, "PHASE 3 — CRASH"),
    (9600, 10800, "PHASE 4 — RECOVERY"),
]

VALID_TYPES = {t.value for t in TimelineEventType}


def parse_time_to_sec(value: str) -> float:
    """Parse simulation clock time into seconds.

    Two-part values are HH:MM (hours and minutes).
    Three-part values are HH:MM:SS.
    """
    parts = [float(p) for p in value.strip().split(":")]
    if len(parts) == 3:
        h, m, s = parts
        return h * 3600 + m * 60 + s
    if len(parts) == 2:
        h, m = parts
        return h * 3600 + m * 60
    raise ValueError(f"invalid time format: {value}")


def format_sim_time(sec: float) -> str:
    sec = max(0, int(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def phase_for_elapsed(elapsed_sec: float) -> str:
    for start, end, name in PHASES:
        if start <= elapsed_sec < end:
            return name
    if elapsed_sec >= SIM_DURATION_SEC:
        return "COMPLETED"
    return PHASES[-1][2]


def load_timeline_json() -> dict[str, Any]:
    with TIMELINE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def validate_timeline(data: dict[str, Any] | None = None) -> list[str]:
    """Return list of validation errors (empty = valid)."""
    errors: list[str] = []
    data = data or load_timeline_json()
    events = data.get("events", [])
    if not events:
        errors.append("timeline contains no events")
        return errors

    keys: set[str] = set()
    ipo_state: dict[str, dict[str, float]] = {}
    dissolved: set[str] = set()
    has_end = False

    for raw in events:
        key = raw.get("idempotency_key") or f"cp_{raw.get('checkpoint_id')}"
        if key in keys:
            errors.append(f"duplicate idempotency_key: {key}")
        keys.add(key)

        try:
            offset = parse_time_to_sec(raw["time"])
        except (KeyError, ValueError) as exc:
            errors.append(f"{key}: invalid time — {exc}")
            continue

        if offset < 0 or offset > SIM_DURATION_SEC:
            errors.append(f"{key}: timestamp {offset}s outside 0–10800")

        etype = raw.get("type")
        if etype not in VALID_TYPES:
            errors.append(f"{key}: invalid event type {etype}")

        payload = raw.get("payload") or {}
        ipo_key = payload.get("ipo_key")

        if etype == TimelineEventType.IPO_OPEN.value:
            for field in ("ticker", "company_name", "issue_price", "lot_size", "total_lots", "winning_lots"):
                if field not in payload:
                    errors.append(f"{key}: IPO_OPEN missing {field}")
            ipo_state[ipo_key or key] = {"open": offset}

        if etype == TimelineEventType.IPO_CLOSE.value and ipo_key:
            ipo_state.setdefault(ipo_key, {})["close"] = offset

        if etype == TimelineEventType.IPO_ALLOTMENT.value and ipo_key:
            ipo_state.setdefault(ipo_key, {})["allot"] = offset

        if etype == TimelineEventType.IPO_LISTING.value and ipo_key:
            ipo_state.setdefault(ipo_key, {})["list"] = offset

        if etype == TimelineEventType.COMPANY_DISSOLUTION.value:
            ticker = payload.get("ticker")
            if not ticker:
                errors.append(f"{key}: dissolution missing ticker")
            elif ticker in dissolved:
                errors.append(f"{key}: duplicate dissolution for {ticker}")
            else:
                dissolved.add(ticker)
            if payload.get("liquidation_price") is None:
                errors.append(f"{key}: dissolution missing liquidation_price")

        if etype == TimelineEventType.SIMULATION_END.value:
            has_end = True
            if abs(offset - SIM_DURATION_SEC) > 1:
                errors.append(f"{key}: SIMULATION_END must be at 03:00:00")

        if etype == TimelineEventType.NEWS.value:
            impacts = payload.get("sector_impacts") or {}
            market = payload.get("market_wide")
            if not impacts and market is None:
                errors.append(f"{key}: NEWS missing sector_impacts or market_wide")

    for ipo_key, state in ipo_state.items():
        if "list" in state and "allot" in state and state["list"] < state["allot"]:
            errors.append(f"IPO {ipo_key}: listing before allotment")
        if "allot" in state and "close" in state and state["allot"] < state["close"]:
            errors.append(f"IPO {ipo_key}: allotment before close")
        if "close" in state and "open" in state and state["close"] < state["open"]:
            errors.append(f"IPO {ipo_key}: close before open")

    if not has_end:
        errors.append("timeline missing SIMULATION_END event")

    return errors


def seed_timeline_from_json(db: Session, *, force: bool = False) -> int:
    """Insert timeline rows from JSON. Returns count inserted."""
    existing = db.scalar(select(func.count(TimelineEvent.id))) or 0
    if existing and not force:
        return 0

    if force and existing:
        db.execute(delete(TimelineEvent))
        db.flush()

    data = load_timeline_json()
    errors = validate_timeline(data)
    if errors:
        raise ValueError("timeline validation failed: " + "; ".join(errors))

    inserted = 0
    for raw in data["events"]:
        offset = parse_time_to_sec(raw["time"])
        event = TimelineEvent(
            checkpoint_id=int(raw["checkpoint_id"]),
            idempotency_key=raw.get("idempotency_key") or f"cp_{raw['checkpoint_id']}",
            sim_offset_sec=offset,
            phase=raw.get("phase") or phase_for_elapsed(offset),
            event_type=TimelineEventType(raw["type"]),
            headline=raw.get("headline") or raw.get("title") or raw["type"],
            description=raw.get("description"),
            payload_json=json.dumps(raw.get("payload") or {}),
            status=TimelineEventStatus.PENDING,
        )
        db.add(event)
        inserted += 1
    db.commit()
    return inserted


def list_timeline_events(db: Session) -> list[TimelineEvent]:
    return list(
        db.scalars(select(TimelineEvent).order_by(TimelineEvent.sim_offset_sec, TimelineEvent.id)).all()
    )


def progress_snapshot(
    db: Session, elapsed_sec: float, *, include_checkpoints: bool = True
) -> dict[str, Any]:
    total = db.scalar(select(func.count(TimelineEvent.id))) or 0
    executed = db.scalar(
        select(func.count(TimelineEvent.id)).where(
            TimelineEvent.status == TimelineEventStatus.EXECUTED
        )
    ) or 0

    if include_checkpoints:
        events = list_timeline_events(db)
        current = None
        nxt = None
        for e in events:
            if e.status == TimelineEventStatus.EXECUTED:
                current = e
            elif e.status == TimelineEventStatus.PENDING and nxt is None:
                nxt = e
                break
        current_cp = current.checkpoint_id if current else None
        checkpoints = [
            _event_dict(e, is_current=e.checkpoint_id == current_cp and current is not None)
            for e in events
        ]
    else:
        current = db.scalar(
            select(TimelineEvent)
            .where(TimelineEvent.status == TimelineEventStatus.EXECUTED)
            .order_by(TimelineEvent.sim_offset_sec.desc(), TimelineEvent.id.desc())
            .limit(1)
        )
        nxt = db.scalar(
            select(TimelineEvent)
            .where(TimelineEvent.status == TimelineEventStatus.PENDING)
            .order_by(TimelineEvent.sim_offset_sec, TimelineEvent.id)
            .limit(1)
        )
        checkpoints = []

    seconds_to_next = None
    if nxt is not None:
        seconds_to_next = max(0.0, nxt.sim_offset_sec - elapsed_sec)
    return {
        "total_checkpoint_count": total,
        "completed_checkpoint_count": executed,
        "current_phase": phase_for_elapsed(elapsed_sec),
        "current_event": _event_dict(current, is_current=True) if current else None,
        "next_event": _event_dict(nxt) if nxt else None,
        "seconds_to_next_event": seconds_to_next,
        "checkpoints": checkpoints,
    }


def _event_dict(event: TimelineEvent | None, *, is_current: bool = False) -> dict[str, Any] | None:
    if event is None:
        return None
    return {
        "id": event.id,
        "checkpoint_id": event.checkpoint_id,
        "timestamp": format_sim_time(event.sim_offset_sec),
        "sim_offset_sec": event.sim_offset_sec,
        "phase": event.phase,
        "type": event.event_type.value,
        "headline": event.headline,
        "status": event.status.value,
        "is_current": is_current,
    }
