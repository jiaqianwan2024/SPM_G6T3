"""SPM-120: one Safety Officer claims an event's safety review

Revision ID: 0012_safety_officer
Revises: 0011_rejection_reason
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_safety_officer"
down_revision = "0011_rejection_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("safety_officer_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "safety_officer_id")
