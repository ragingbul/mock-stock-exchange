"""Centralized timeline event processor — sole trigger for scheduled events."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import NewsEvent, Stock
from app.models.enums import SimulationStatus, TimelineEventStatus, TimelineEventType
from app.models.simulation_event_log import SimulationEventLog
from app.models.timeline_event import TimelineEvent
from app.services import ipo_service, news_service
from app.services.dissolution_service import DissolutionError, dissolve_company
from app.services.simulation_clock import get_or_create_state

logger = logging.getLogger(__name__)


def _log(db: Session, *, elapsed: float, event_type: str, detail: dict) -> None:
    db.add(
        SimulationEventLog(
            sim_elapsed_sec=elapsed,
            event_type=event_type,
            detail_json=json.dumps(detail),
        )
    )


def process_due_events(db: Session, elapsed_sec: float) -> list[dict]:
    """Execute all pending timeline events with sim_offset_sec <= elapsed_sec."""
    state = get_or_create_state(db)
    if state.status != SimulationStatus.RUNNING:
        return []

    due = list(
        db.scalars(
            select(TimelineEvent)
            .where(
                TimelineEvent.status == TimelineEventStatus.PENDING,
                TimelineEvent.sim_offset_sec <= elapsed_sec,
            )
            .order_by(TimelineEvent.sim_offset_sec, TimelineEvent.id)
        ).all()
    )

    results: list[dict] = []
    for event in due:
        if event.status == TimelineEventStatus.EXECUTED:
            continue
        try:
            payload = json.loads(event.payload_json or "{}")
            outcome = _dispatch(db, event, payload, elapsed_sec)
            event.status = TimelineEventStatus.EXECUTED
            event.executed_at = datetime.now(timezone.utc)
            _log(
                db,
                elapsed=elapsed_sec,
                event_type=event.event_type.value,
                detail={"checkpoint_id": event.checkpoint_id, "headline": event.headline, **outcome},
            )
            db.commit()
            results.append(
                {
                    "checkpoint_id": event.checkpoint_id,
                    "type": event.event_type.value,
                    "headline": event.headline,
                    **outcome,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("EventProcessor failed checkpoint %s", event.checkpoint_id)
            db.rollback()
            _log(
                db,
                elapsed=elapsed_sec,
                event_type="EVENT_FAILED",
                detail={"checkpoint_id": event.checkpoint_id, "error": str(exc)},
            )
            db.commit()
    return results


def _dispatch(db: Session, event: TimelineEvent, payload: dict, elapsed_sec: float) -> dict:
    et = event.event_type
    if et == TimelineEventType.NEWS:
        return _handle_news(db, event, payload)
    if et == TimelineEventType.IPO_OPEN:
        return _handle_ipo_open(db, payload)
    if et == TimelineEventType.IPO_CLOSE:
        return _handle_ipo_close(db, payload)
    if et == TimelineEventType.IPO_ALLOTMENT:
        return _handle_ipo_allotment(db, payload)
    if et == TimelineEventType.IPO_LISTING:
        return _handle_ipo_listing(db, payload)
    if et == TimelineEventType.COMPANY_DISSOLUTION:
        return _handle_dissolution(db, event, payload)
    if et == TimelineEventType.SIMULATION_END:
        return _handle_simulation_end(db)
    raise ValueError(f"unknown event type: {et}")


def _news_direction(payload: dict) -> int:
    market_wide = payload.get("market_wide")
    sector_impacts = payload.get("sector_impacts") or {}
    if market_wide is not None:
        return 1 if float(market_wide) >= 0 else -1
    if sector_impacts:
        net = sum(float(v) for v in sector_impacts.values())
        return 1 if net >= 0 else -1
    return 1


def _handle_news(db: Session, event: TimelineEvent, payload: dict) -> dict:
    sector_impacts = payload.get("sector_impacts") or {}
    market_wide = payload.get("market_wide")
    brief_points = payload.get("brief_points") or []
    news = news_service.create_news(
        db,
        title=event.headline,
        description=event.description or "",
        brief_points=brief_points,
        sector_impacts=sector_impacts,
        market_wide_impact_pct=market_wide,
        market_wide=market_wide is not None,
        direction=_news_direction(payload),
        impact=Decimal("1"),
        confidence=Decimal("1"),
        duration_minutes=9999,
        decay_rate=Decimal("0.001"),
        status="scheduled",
    )
    news_service.release_news(db, news.id)
    detail = news_service.news_detail_dict(news)
    return {"news_id": news.id, "broadcast": detail}


def _handle_ipo_open(db: Session, payload: dict) -> dict:
    from app.models.ipo import IPO, IPOStatus
    from app.seed.tradeverse_stocks import resolve_ipo_sector_id

    key = payload.get("ipo_key") or payload["ticker"]
    sector_id = payload.get("sector_id") or resolve_ipo_sector_id(db, payload["ticker"])
    existing = db.scalar(select(IPO).where(IPO.timeline_key == key))
    if existing is None:
        ipo = ipo_service.create_ipo(
            db,
            company_name=payload["company_name"],
            ticker=payload["ticker"],
            sector_id=sector_id,
            issue_price=payload["issue_price"],
            lot_size=payload["lot_size"],
            total_lots=payload["total_lots"],
            winning_lots=payload["winning_lots"],
            maximum_lots_per_user=payload.get("maximum_lots_per_user", 2),
            status=IPOStatus.DRAFT,
            description=payload.get("description"),
        )
        ipo.timeline_key = key
        db.commit()
    else:
        ipo = existing
    ipo = ipo_service.open_ipo(db, ipo.id)
    return {"ipo_id": ipo.id, "ticker": ipo.ticker, "status": ipo.status.value}


def _handle_ipo_close(db: Session, payload: dict) -> dict:
    from app.models.ipo import IPO

    ipo = _find_ipo(db, payload)
    ipo = ipo_service.close_applications(db, ipo.id)
    return {"ipo_id": ipo.id, "status": ipo.status.value}


def _handle_ipo_allotment(db: Session, payload: dict) -> dict:
    from app.services.simulation_settings_service import get_or_create_settings

    ipo = _find_ipo(db, payload)
    settings = get_or_create_settings(db)
    result = ipo_service.allot_ipo(db, ipo.id, seed=int(settings.simulation_seed))
    return result


def _handle_ipo_listing(db: Session, payload: dict) -> dict:
    ipo = _find_ipo(db, payload)
    result = ipo_service.list_ipo(db, ipo.id)
    return result


def _handle_dissolution(db: Session, event: TimelineEvent, payload: dict) -> dict:
    try:
        return dissolve_company(
            db,
            ticker=payload["ticker"],
            liquidation_price=payload["liquidation_price"],
            headline=event.headline,
        )
    except DissolutionError as exc:
        raise ValueError(str(exc)) from exc


def _handle_simulation_end(db: Session) -> dict:
    from app.models.enums import SimulationStatus
    from app.services.simulation_clock import get_or_create_state

    state = get_or_create_state(db)
    state.status = SimulationStatus.COMPLETED
    db.commit()
    return {"completed": True}


def _find_ipo(db: Session, payload: dict):
    from app.models.ipo import IPO

    key = payload.get("ipo_key")
    ticker = payload.get("ticker")
    if key:
        ipo = db.scalar(select(IPO).where(IPO.timeline_key == key))
        if ipo:
            return ipo
    if ticker:
        ipo = db.scalar(select(IPO).where(IPO.ticker == ticker.upper()).order_by(IPO.id.desc()))
        if ipo:
            return ipo
    raise ValueError(f"IPO not found for payload {payload}")
