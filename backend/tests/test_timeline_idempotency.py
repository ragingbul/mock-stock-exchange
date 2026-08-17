"""Timeline event idempotency."""

from app.models.enums import TimelineEventStatus
from app.services.event_processor import process_due_events
from app.services.simulation_controller import reset_simulation, start_simulation


def test_executed_timeline_event_not_replayed(db_session):
    reset_simulation(db_session)
    start_simulation(db_session)
    # First checkpoint is at 00:03 (180 sim-seconds)
    first = process_due_events(db_session, 180.0)
    assert first, "expected at least one due event at t=180"
    checkpoint_id = first[0]["checkpoint_id"]

    from app.models import TimelineEvent

    event = db_session.query(TimelineEvent).filter(TimelineEvent.checkpoint_id == checkpoint_id).one()
    assert event.status == TimelineEventStatus.EXECUTED

    second = process_due_events(db_session, 180.0)
    replayed = [r for r in second if r.get("checkpoint_id") == checkpoint_id]
    assert not replayed
