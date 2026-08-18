"""Shared pytest fixtures — in-memory SQLite so tests need no Postgres."""

from __future__ import annotations

import app.models  # noqa: F401 — register metadata
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.exchange.book_registry import books
from app.main import create_app


def join_participant(client: TestClient, display_name: str = "Tester") -> tuple[int, dict[str, str]]:
    res = client.post("/api/v1/auth/join", json={"display_name": display_name})
    assert res.status_code == 200, res.text
    data = res.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return data["trader_id"], headers


def _make_memory_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture()
def db_session() -> Session:
    get_settings.cache_clear()
    books.clear()
    engine = _make_memory_engine()
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        from app.models.enums import SimulationStatus
        from app.services.simulation_clock import get_or_create_state

        state = get_or_create_state(session)
        state.status = SimulationStatus.RUNNING
        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        books.clear()
        get_settings.cache_clear()


@pytest.fixture()
def client() -> TestClient:
    get_settings.cache_clear()
    books.clear()
    engine = _make_memory_engine()
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)

    app = create_app()
    settings = get_settings()

    def _override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    headers = {"Authorization": f"Bearer {settings.admin_secret}"}
    with TestClient(app, headers=headers) as test_client:
        db = TestingSession()
        from app.models.enums import SimulationStatus
        from app.services.simulation_clock import get_or_create_state

        state = get_or_create_state(db)
        state.status = SimulationStatus.RUNNING
        db.commit()
        db.close()
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    books.clear()
    get_settings.cache_clear()
