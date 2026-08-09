"""Health endpoint tests."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_root() -> None:
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == 1
    assert "Mock Stock Exchange" in body["message"]


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] == 1


def test_ready_returns_status() -> None:
    """Ready may be degraded if Postgres is not running — still a valid response."""
    client = TestClient(create_app())
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "degraded"}
    assert body["database"] in {"up", "down"}
    assert body["phase"] == 1


def test_settings_database_url() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.postgres_db == "mock_stock_exchange"
    assert settings.default_starting_capital == 1_000_000.0
