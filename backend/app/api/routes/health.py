"""Health and readiness endpoints."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_database_connection
from app.services.simulation_clock import get_or_create_state
from app.services import simulation_engine
from app.core.database import SessionLocal
from app.models.enums import SimulationStatus

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe — process is up."""
    settings = get_settings()
    db_ok = check_database_connection()
    sim_status = "unknown"
    engine = "inactive"
    try:
        with SessionLocal() as db:
            state = get_or_create_state(db)
            sim_status = state.status.value
        engine = "active" if simulation_engine.engine_status().get("running") else "inactive"
    except Exception:
        sim_status = "unknown"
    return {
        "status": "ok" if db_ok else "degraded",
        "service": settings.app_name,
        "env": settings.app_env,
        "database": "ok" if db_ok else "down",
        "simulation": sim_status,
        "engine": engine,
    }


@router.get("/ready")
def ready() -> dict:
    """Readiness probe — dependencies (DB) are reachable when available."""
    db_ok = check_database_connection()
    running = False
    try:
        with SessionLocal() as db:
            state = get_or_create_state(db)
            running = state.status == SimulationStatus.RUNNING
    except Exception:
        pass
    return {
        "status": "ready" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
        "simulation_running": running,
    }
