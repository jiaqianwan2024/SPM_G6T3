"""Store each event category the way the organiser form spells it, so "meeting" and "Meeting" are one

Revision ID: 0016_category_casing
Revises: 0015_change_request_narrower
Create Date: 2026-11-01
"""

from alembic import op

revision = "0016_category_casing"
down_revision = "0015_change_request_narrower"
branch_labels = None
depends_on = None

CATEGORIES = ("Conference", "Workshop", "Networking", "Meeting")


def upgrade() -> None:
    for name in CATEGORIES:
        op.execute(
            f"UPDATE events SET category = '{name}' "
            f"WHERE LOWER(TRIM(category)) = '{name.lower()}' AND category <> '{name}'"
        )


def downgrade() -> None:
    # The original casing is not kept, and the standard spelling is valid either way.
    pass
