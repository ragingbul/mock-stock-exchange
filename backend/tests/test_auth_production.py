"""Production registration restrictions."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.exchange.book_registry import books
from app.main import create_app
from tests.conftest import _make_memory_engine, join_participant


def test_open_trader_post_blocked_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    books.clear()
    engine = _make_memory_engine()
    from sqlalchemy.orm import sessionmaker

    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)
    app = create_app()

    def _override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as client:
        res = client.post("/api/v1/traders", json={"name": "Sneaky"})
        assert res.status_code in {401, 403}
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    books.clear()
    get_settings.cache_clear()


def test_join_flow_still_works_in_production(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    trader_id, auth = join_participant(client, "Participant")
    assert trader_id > 0
    assert "Authorization" in auth
    get_settings.cache_clear()
