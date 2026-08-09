"""Application configuration.

All tunables live here (or in environment variables) so later phases can change
behaviour without touching exchange mechanics.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment / .env files."""

    model_config = SettingsConfigDict(
        # Prefer repo-root .env when running from backend/; also allow backend/.env
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Mock Stock Exchange"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # CORS — frontend origin(s)
    cors_origins: str = "http://localhost:3000"

    # Database (PostgreSQL)
    postgres_user: str = "mse"
    postgres_password: str = "mse_dev_password"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "mock_stock_exchange"

    # Auth (simple event-auth; replaceable later)
    auth_secret_key: str = "change-me-in-production-phase-0"
    auth_token_expire_minutes: int = 60 * 12

    # Market defaults (used from Phase 1 onward)
    default_starting_capital: float = 1_000_000.0
    default_tick_size: float = 0.05
    default_circuit_pct: float = 0.10
    random_seed: int = 42

    @property
    def database_url(self) -> str:
        """SQLAlchemy async-compatible sync URL for PostgreSQL."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
