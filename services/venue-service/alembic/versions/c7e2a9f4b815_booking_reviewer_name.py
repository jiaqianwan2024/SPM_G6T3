"""SPM-8 AC5: an approval records who approved it by name, as well as by id and time.

Revision ID: c7e2a9f4b815
Revises: b6c1d8e4a902
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c7e2a9f4b815"
down_revision: Union[str, None] = "b6c1d8e4a902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("venue_bookings", sa.Column("reviewed_by_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("venue_bookings", "reviewed_by_name")
