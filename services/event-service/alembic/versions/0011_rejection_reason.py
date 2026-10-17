"""SPM-70: a rejection records its listed reason beside the explanation

Revision ID: 0011_rejection_reason
Revises: 0010_safety_handoff
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_rejection_reason"
down_revision = "0010_safety_handoff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event_reviews", sa.Column("reason", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("event_reviews", "reason")
