"""Store each known event category in one spelling

The API used to keep a category exactly as sent, so "meeting" and "Meeting"
showed as two categories in the filters. Known categories are now stored in
their listed spelling; this brings existing rows into line.

Revision ID: 0016_category_spelling
Revises: 0015_change_request_narrower
Create Date: 2026-11-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_category_spelling"
down_revision = "0015_change_request_narrower"
branch_labels = None
depends_on = None

# The same list as app/schemas/event.py EVENT_CATEGORIES, copied so the
# migration keeps working if that list later changes.
CATEGORIES = ("Conference", "Workshop", "Networking", "Meeting")


def upgrade() -> None:
    for name in CATEGORIES:
        op.execute(
            sa.text("UPDATE events SET category = :name WHERE LOWER(TRIM(category)) = :lower").bindparams(
                name=name, lower=name.lower()
            )
        )


def downgrade() -> None:
    # The original spellings were not kept, and the listed one is valid either way.
    pass
