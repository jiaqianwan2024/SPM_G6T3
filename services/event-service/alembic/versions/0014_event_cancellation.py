"""SPM-88: a cancelled event keeps why it was cancelled, by whom, and when

Revision ID: 0014_event_cancellation
Revises: 0013_event_reschedules
Create Date: 2026-10-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_event_cancellation"
down_revision = "0013_event_reschedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("cancelled_by", sa.String(64), nullable=True))
    op.add_column("events", sa.Column("cancelled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "cancelled_at")
    op.drop_column("events", "cancelled_by")
    op.drop_column("events", "cancellation_reason")
