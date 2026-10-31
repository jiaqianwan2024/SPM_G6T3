"""SPM-85: a declined change request records whether a narrower one was asked for

Revision ID: 0015_change_request_narrower
Revises: 0014_event_cancellation
Create Date: 2026-10-31
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_change_request_narrower"
down_revision = "0014_event_cancellation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_change_requests",
        sa.Column("narrower_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("event_change_requests", "narrower_requested")
