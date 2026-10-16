"""SPM-10 AC3: a rejection can suggest another venue, kept by id and by name.

Revision ID: e1d5c3a8b247
Revises: c7e2a9f4b815
Create Date: 2026-10-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e1d5c3a8b247"
down_revision: Union[str, None] = "c7e2a9f4b815"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("venue_bookings", sa.Column("suggested_venue_id", sa.String(length=64), nullable=True))
    op.add_column("venue_bookings", sa.Column("suggested_venue_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("venue_bookings", "suggested_venue_name")
    op.drop_column("venue_bookings", "suggested_venue_id")
