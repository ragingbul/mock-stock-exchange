"""SIMULATION_SPEED env override precedence."""

import os

import pytest

from app.services.simulation_clock import get_or_create_state
from app.services.simulation_settings_service import (
    apply_simulation_speed_override_if_set,
    get_or_create_settings,
    sync_runtime_speed_from_settings,
    update_settings,
)


def test_env_override_only_when_explicitly_set(db_session, monkeypatch):
    update_settings(db_session, sim_speed_multiplier=12.0)
    monkeypatch.delenv("SIMULATION_SPEED", raising=False)
    assert apply_simulation_speed_override_if_set(db_session) is False
    assert float(get_or_create_settings(db_session).sim_speed_multiplier) == 12.0


def test_explicit_env_overrides_db(db_session, monkeypatch):
    update_settings(db_session, sim_speed_multiplier=1.0)
    monkeypatch.setenv("SIMULATION_SPEED", "60")
    get_settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings
    get_settings.cache_clear()
    assert apply_simulation_speed_override_if_set(db_session) is True
    assert float(get_or_create_settings(db_session).sim_speed_multiplier) == 60.0
    get_settings.cache_clear()


def test_sync_runtime_speed_copies_settings_to_state(db_session, monkeypatch):
    monkeypatch.delenv("SIMULATION_SPEED", raising=False)
    update_settings(db_session, sim_speed_multiplier=25.0)
    speed = sync_runtime_speed_from_settings(db_session)
    state = get_or_create_state(db_session)
    assert speed == 25.0
    assert float(state.sim_speed_multiplier) == 25.0


def test_reset_applies_env_when_set(client, monkeypatch):
    monkeypatch.setenv("SIMULATION_SPEED", "60")
    from app.core.config import get_settings

    get_settings.cache_clear()
    res = client.post("/api/v1/admin/simulation/reset")
    assert res.status_code == 200
    status = client.get("/api/v1/admin/simulation/status").json()
    assert float(status["sim_speed_multiplier"]) == 60.0
    get_settings.cache_clear()
