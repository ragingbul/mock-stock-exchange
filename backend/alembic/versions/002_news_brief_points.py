"""Add brief_points_json to news_events."""

from alembic import op
import sqlalchemy as sa

revision = "002_news_brief_points"
down_revision = "001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_events",
        sa.Column("brief_points_json", sa.Text(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("news_events", "brief_points_json")
