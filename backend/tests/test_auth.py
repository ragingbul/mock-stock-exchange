"""Admin route authorization tests."""

from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_admin_start_requires_auth():
    from app.core.database import get_db
    from app.main import create_app

    get_settings.cache_clear()
    app = create_app()

    def _override_db():
        from sqlalchemy.orm import sessionmaker

        from app.core.database import Base
        from tests.conftest import _make_memory_engine

        engine = _make_memory_engine()
        TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
        Base.metadata.create_all(bind=engine)
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as bare_client:
        res = bare_client.post("/api/v1/admin/simulation/start")
        assert res.status_code == 401
    app.dependency_overrides.clear()


def test_admin_start_with_secret(client: TestClient):
    settings = get_settings()
    res = client.post(
        "/api/v1/admin/simulation/start",
        headers={"Authorization": f"Bearer {settings.admin_secret}"},
    )
    assert res.status_code in {200, 400}


def test_auth_join_returns_token(client: TestClient):
    res = client.post("/api/v1/auth/join", json={"display_name": "Tester"})
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["trader_id"] > 0
