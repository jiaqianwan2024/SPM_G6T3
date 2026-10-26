"""cleared_from_bell: lets the bell's "Clear all" hide notifications without deleting them

Revision ID: 0003_cleared_from_bell
Revises: 0002_publish_columns
Create Date: 2026-10-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_cleared_from_bell"
down_revision = "0002_publish_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("cleared_from_bell", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("notifications", "cleared_from_bell")
