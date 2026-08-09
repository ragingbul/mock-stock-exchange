"""Mock Stock Exchange API — Phase 0 foundation."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Simulated multiplayer stock exchange. "
            "Order books and the matching engine discover prices; "
            "models and news influence trader behaviour only."
        ),
        version="0.0.1",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=settings.api_prefix)

    @app.get("/")
    def root() -> dict:
        return {
            "message": settings.app_name,
            "phase": 0,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    return app


app = create_app()
