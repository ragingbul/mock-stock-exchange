"""Accelerated timeline integration test — 3h sim in seconds."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import TimelineEvent
from app.models.enums import SimulationStatus, TimelineEventStatus
from app.services.event_processor import process_due_events
from app.services.simulation_controller import reset_simulation, start_simulation, stop_simulation
from app.services.simulation_clock import advance_clock, get_or_create_state
from app.services.simulation_settings_service import update_settings
from app.services.timeline_service import seed_timeline_from_json


def test_accelerated_timeline_executes_all_checkpoints(db_session):
    seed_timeline_from_json(db_session, force=True)
    reset_simulation(db_session)
    update_settings(db_session, sim_speed_multiplier=3600.0)
    start_simulation(db_session)

    total = db_session.scalar(select(func.count(TimelineEvent.id))) or 0
    assert total >= 50

    for _ in range(200):
        state = get_or_create_state(db_session)
        if state.status == SimulationStatus.COMPLETED:
            break
        advance_clock(db_session, 60.0 / float(state.sim_speed_multiplier or 1))
        state = get_or_create_state(db_session)
        process_due_events(db_session, float(state.sim_elapsed_sec))
        if float(state.sim_elapsed_sec) >= float(state.sim_duration_sec):
            state.status = SimulationStatus.COMPLETED
            db_session.commit()
            break

    executed = db_session.scalar(
        select(func.count(TimelineEvent.id)).where(
            TimelineEvent.status == TimelineEventStatus.EXECUTED
        )
    ) or 0
    assert executed == total
    assert get_or_create_state(db_session).status == SimulationStatus.COMPLETED


def test_stop_freezes_timeline_progress(db_session):
    seed_timeline_from_json(db_session, force=True)
    reset_simulation(db_session)
    start_simulation(db_session)

    for _ in range(5):
        advance_clock(db_session, 30.0)
        process_due_events(db_session, float(get_or_create_state(db_session).sim_elapsed_sec))

    elapsed_at_stop = float(get_or_create_state(db_session).sim_elapsed_sec)
    executed_at_stop = db_session.scalar(
        select(func.count(TimelineEvent.id)).where(
            TimelineEvent.status == TimelineEventStatus.EXECUTED
        )
    ) or 0

    stop_simulation(db_session)
    advance_clock(db_session, 300.0)
    process_due_events(db_session, float(get_or_create_state(db_session).sim_elapsed_sec))

    assert float(get_or_create_state(db_session).sim_elapsed_sec) == elapsed_at_stop
    executed_after = db_session.scalar(
        select(func.count(TimelineEvent.id)).where(
            TimelineEvent.status == TimelineEventStatus.EXECUTED
        )
    ) or 0
    assert executed_after == executed_at_stop
