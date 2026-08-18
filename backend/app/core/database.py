"""Database engine and session factory."""

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


def _sqlite_connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {"connect_timeout": 2}


def create_db_engine(url: str | None = None) -> Engine:
    settings = get_settings()
    database_url = url or settings.database_url
    connect_args = _sqlite_connect_args(database_url)
    engine_kwargs: dict = {
        "pool_pre_ping": not database_url.startswith("sqlite"),
        "future": True,
        "connect_args": connect_args,
    }
    if not database_url.startswith("sqlite"):
        engine_kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=settings.db_pool_recycle,
            pool_timeout=settings.db_pool_timeout,
        )
    engine = create_engine(database_url, **engine_kwargs)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Return True if a simple SELECT 1 succeeds."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def init_db(target_engine: Engine | None = None) -> None:
    """Create tables. Import models so metadata is registered."""
    import app.models  # noqa: F401

    bind = target_engine or engine
    Base.metadata.create_all(bind=bind)
    _ensure_sqlite_columns(bind)


def _ensure_sqlite_columns(bind: Engine) -> None:
    """Add newly introduced columns on existing SQLite databases."""
    url = str(bind.url)
    if not url.startswith("sqlite"):
        return
    with bind.connect() as conn:
        def _cols(table: str) -> set[str]:
            try:
                return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
            except Exception:
                return set()

        stock_cols = _cols("stocks")
        if stock_cols and "sector_id" not in stock_cols:
            conn.execute(text("ALTER TABLE stocks ADD COLUMN sector_id INTEGER"))

        trader_cols = _cols("traders")
        if trader_cols and "cash_blocked_ipo" not in trader_cols:
            conn.execute(
                text("ALTER TABLE traders ADD COLUMN cash_blocked_ipo NUMERIC(18,2) DEFAULT 0")
            )

        news_cols = _cols("news_events")
        alters = [
            ("market_wide_impact_pct", "NUMERIC(8,4)"),
            ("sector_impacts_json", "TEXT DEFAULT '{}'"),
            ("stock_impacts_json", "TEXT DEFAULT '{}'"),
            ("status", "VARCHAR(32) DEFAULT 'draft'"),
            ("baseline_prices_json", "TEXT DEFAULT '{}'"),
        ]
        if news_cols:
            for name, decl in alters:
                if name not in news_cols:
                    conn.execute(text(f"ALTER TABLE news_events ADD COLUMN {name} {decl}"))

        stock_cols = _cols("stocks")
        if stock_cols and "status" not in stock_cols:
            conn.execute(text("ALTER TABLE stocks ADD COLUMN status VARCHAR(32) DEFAULT 'active'"))
        if stock_cols and "liquidation_price" not in stock_cols:
            conn.execute(text("ALTER TABLE stocks ADD COLUMN liquidation_price NUMERIC(18,4)"))

        ipo_cols = _cols("ipos")
        if ipo_cols and "timeline_key" not in ipo_cols:
            conn.execute(text("ALTER TABLE ipos ADD COLUMN timeline_key VARCHAR(64)"))

        settings_cols = _cols("simulation_settings")
        settings_alters = [
            ("sim_duration_sec", "FLOAT DEFAULT 10800"),
            ("sim_speed_multiplier", "FLOAT DEFAULT 1"),
            ("simulation_seed", "INTEGER DEFAULT 42"),
            ("simulation_ai_enabled", "BOOLEAN DEFAULT 1"),
        ]
        if settings_cols:
            for name, decl in settings_alters:
                if name not in settings_cols:
                    conn.execute(text(f"ALTER TABLE simulation_settings ADD COLUMN {name} {decl}"))

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS sectors (
                    id INTEGER NOT NULL PRIMARY KEY,
                    slug VARCHAR(64) NOT NULL UNIQUE,
                    name VARCHAR(128) NOT NULL,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.commit()
