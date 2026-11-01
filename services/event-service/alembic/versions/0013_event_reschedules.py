"""SPM-87: record each reschedule with its old and new period and the reason

Revision ID: 0013_event_reschedules
Revises: 0012_safety_officer
Create Date: 2026-10-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_event_reschedules"
down_revision = "0012_safety_officer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_reschedules",
        sa.Column("reschedule_id", sa.String(64), primary_key=True),
        sa.Column("event_id", sa.String(64), sa.ForeignKey("events.event_id"), nullable=False, index=True),
        sa.Column("old_start_at", sa.DateTime(), nullable=True),
        sa.Column("old_end_at", sa.DateTime(), nullable=True),
        sa.Column("new_start_at", sa.DateTime(), nullable=False),
        sa.Column("new_end_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("rescheduled_by", sa.String(64), nullable=False),
        sa.Column("rescheduled_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("event_reschedules")
