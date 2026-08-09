"""Mock Stock Exchange API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, health, market, orders, stocks, traders, ws
from app.core.config import get_settings
from app.core.database import check_database_connection, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
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
        version="1.0.0",
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

    prefix = settings.api_prefix
    app.include_router(health.router, prefix=prefix)
    app.include_router(traders.router, prefix=prefix)
    app.include_router(stocks.router, prefix=prefix)
    app.include_router(orders.router, prefix=prefix)
    app.include_router(market.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)
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
