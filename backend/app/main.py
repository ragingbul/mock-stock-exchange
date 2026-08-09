"""Mock Stock Exchange API — Phase 1 core entities."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, stocks, traders
from app.core.config import get_settings
from app.core.database import check_database_connection, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create tables when the database is reachable (Postgres or override URL).
    if check_database_connection():
        init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Simulated multiplayer stock exchange. "
            "Order books and the matching engine discover prices; "
            "models and news influence trader behaviour only."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(traders.router, prefix=settings.api_prefix)
    app.include_router(stocks.router, prefix=settings.api_prefix)

    @app.get("/")
    def root() -> dict:
        return {
            "message": settings.app_name,
            "phase": 1,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return app


app = create_app()
