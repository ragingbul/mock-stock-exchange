"""Baseline schema from SQLAlchemy models."""

from alembic import op
import sqlalchemy as sa

revision = "001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from app.core.database import Base
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from app.core.database import Base
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=bind)
