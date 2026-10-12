"""link, resource and occurrence columns for published notifications

Revision ID: 0002_publish_columns
Revises: 0001_initial
Create Date: 2026-10-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_publish_columns"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("link", sa.String(255), nullable=True))
    op.add_column("notifications", sa.Column("resource_type", sa.String(64), nullable=True))
    op.add_column("notifications", sa.Column("resource_id", sa.String(64), nullable=True))
    op.add_column("notifications", sa.Column("occurrence_id", sa.String(128), nullable=True))
    op.create_unique_constraint(
        "uq_notification_occurrence_user", "notifications", ["occurrence_id", "user_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_notification_occurrence_user", "notifications", type_="unique")
    op.drop_column("notifications", "occurrence_id")
    op.drop_column("notifications", "resource_id")
    op.drop_column("notifications", "resource_type")
    op.drop_column("notifications", "link")
