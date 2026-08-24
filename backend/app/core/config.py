"""Application configuration.

All tunables live here (or in environment variables) so later phases can change
behaviour without touching exchange mechanics.
"""

from functools import lru_cache

from pydantic import Field
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
    app_env: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = True
    api_prefix: str = "/api/v1"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_url: str = Field(default="http://localhost:8000", validation_alias="BACKEND_URL")
    frontend_url: str = Field(default="http://localhost:3000", validation_alias="FRONTEND_URL")

    # CORS — frontend origin(s); include common dev ports
    cors_origins: str = Field(
        default=(
            "http://localhost:3000,http://localhost:3001,"
            "http://127.0.0.1:3000,http://127.0.0.1:3001"
        ),
        validation_alias="CORS_ORIGINS",
    )

    # Database (PostgreSQL by default; override with DATABASE_URL for tests/sqlite)
    postgres_user: str = "mse"
    postgres_password: str = "mse_dev_password"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "mock_stock_exchange"
    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")
    db_pool_size: int = Field(default=5, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, validation_alias="DB_MAX_OVERFLOW")
    db_pool_recycle: int = Field(default=1800, validation_alias="DB_POOL_RECYCLE")
    db_pool_timeout: int = Field(default=30, validation_alias="DB_POOL_TIMEOUT")
    auto_init_db: bool = Field(default=True, validation_alias="AUTO_INIT_DB")

    # Auth (simple event-auth; replaceable later)
    auth_secret_key: str = Field(
        default="change-me-in-production-phase-0",
        validation_alias="JWT_SECRET",
    )
    admin_secret: str = Field(
        default="change-me-admin-secret",
        validation_alias="ADMIN_SECRET",
    )
    auth_token_expire_minutes: int = 60 * 12
    rate_limit_per_minute: int = Field(default=600, validation_alias="RATE_LIMIT_PER_MINUTE")

    # Market defaults (used from Phase 1 onward)
    default_starting_capital: float = 1_000_000.0
    max_position_per_stock: int = Field(default=100, validation_alias="MAX_POSITION_PER_STOCK")
    default_tick_size: float = 0.05
    default_circuit_pct: float = 0.10
    random_seed: int = 42
    simulation_speed: float = Field(default=1.0, validation_alias="SIMULATION_SPEED")

    # Event volatility — amplify news/AI reactions for larger swings
    market_intensity_multiplier: float = 3.0
    news_pressure_amplifier: float = 2.5
    news_pressure_cap: float = 3.0
    news_fundamental_multiplier: float = 2.0
    news_decay_tail_factor: float = 0.35
    mm_spread_bps: float = 140.0
    mm_quote_size: int = 35
    mm_min_book_depth: int = 20
    market_noise_std: float = 0.08
    market_news_weight: float = 0.45

    ai_tick_min_sec: float = 15.0
    ai_tick_max_sec: float = 30.0
    news_impact_tolerance_pct: float = 0.5
    news_combined_impact_cap_pct: float = 20.0

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def database_url(self) -> str:
        """SQLAlchemy database URL."""
        url = self.database_url_override
        if not url:
            return (
                f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://") :]
        if url.startswith("postgresql://") and "+psycopg" not in url:
            return "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if self.frontend_url and self.frontend_url not in origins:
            origins.append(self.frontend_url.rstrip("/"))
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
