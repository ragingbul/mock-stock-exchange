"""Health and readiness endpoints."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe — process is up."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
        "phase": 14,
    }


@router.get("/ready")
def ready() -> dict:
    """Readiness probe — dependencies (DB) are reachable when available."""
    db_ok = check_database_connection()
    return {
        "status": "ready" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
        "phase": 14,
    }
