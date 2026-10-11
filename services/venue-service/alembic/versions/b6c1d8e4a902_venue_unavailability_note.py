"""SPM-9: an optional note on a venue unavailability block.

Revision ID: b6c1d8e4a902
Revises: f2a9c4d7e1b6
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b6c1d8e4a902"
down_revision: Union[str, None] = "f2a9c4d7e1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("venue_unavailability", sa.Column("note", sa.Text(), nullable=True))
    op.execute("UPDATE venue_unavailability SET note = '' WHERE note IS NULL")
    op.alter_column("venue_unavailability", "note", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.drop_column("venue_unavailability", "note")
