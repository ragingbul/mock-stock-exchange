"""Mock Stock Exchange API."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    admin,
    auth,
    conditionals,
    health,
    ipos,
    market,
    orders,
    sectors,
    session,
    stocks,
    traders,
    ws,
)
from app.core.config import get_settings
from app.core.database import check_database_connection, init_db
from app.core.security import require_admin

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    logger.info("SERVER START: %s (env=%s)", settings.app_name, settings.app_env)
    if settings.is_production and any(
        "localhost" in origin or "127.0.0.1" in origin for origin in settings.cors_origin_list
    ):
        logger.warning("CORS_ORIGINS contains localhost in production — update to deployed frontend URL")
    if check_database_connection():
        logger.info("DATABASE CONNECTED")
        if settings.auto_init_db and not settings.is_production:
            init_db()
            logger.info("Development schema initialized")
    else:
        logger.error("Database connection failed at startup")

    from app.services import simulation_engine

    simulation_engine.start_engine()
    logger.info("SIMULATION WORKER START requested")
    yield
    simulation_engine.stop_engine()
    logger.info("Server shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Simulated multiplayer stock exchange. "
            "Order books and the matching engine discover prices; "
            "models and news influence trader behaviour only."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    cors_kwargs: dict = {
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.is_production:
        cors_kwargs["allow_origins"] = settings.cors_origin_list
    else:
        cors_kwargs["allow_origins"] = settings.cors_origin_list
        cors_kwargs["allow_origin_regex"] = (
            r"https?://(localhost|127\.0\.0\.1|\d{1,3}(?:\.\d{1,3}){3})(:\d+)?"
        )

    app.add_middleware(CORSMiddleware, **cors_kwargs)

    prefix = settings.api_prefix
    app.include_router(health.router, prefix=prefix)
    app.include_router(auth.router, prefix=prefix)
    app.include_router(session.router, prefix=prefix)
    app.include_router(traders.router, prefix=prefix)
    app.include_router(stocks.router, prefix=prefix)
    app.include_router(sectors.router, prefix=prefix)
    app.include_router(orders.router, prefix=prefix)
    app.include_router(conditionals.router, prefix=prefix)
    app.include_router(ipos.router, prefix=prefix)
    app.include_router(market.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix, dependencies=[Depends(require_admin)])
    app.include_router(ws.router, prefix=prefix)

    @app.get("/")
    def root() -> dict:
        return {
            "message": settings.app_name,
            "phase": 14,
            "docs": "/docs",
            "health": f"{prefix}/health",
            "ws": f"{prefix}/ws",
        }

    return app


app = create_app()
