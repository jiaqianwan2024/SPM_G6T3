"""Join the two category-spelling fixes into one history

0016_category_casing (dev) and 0016_category_spelling (final_tests) were written
separately on the same day, both after 0015, and both make each known category
use its listed spelling. With both present Alembic had two heads and
`alembic upgrade head` refused to run. This revision has both as parents, so a
database at either one, or at 0015, upgrades to a single head. The two updates
do the same thing, so running both is harmless.

Revision ID: 0017_merge_category_fixes
Revises: 0016_category_casing, 0016_category_spelling
Create Date: 2026-11-01
"""

revision = "0017_merge_category_fixes"
down_revision = ("0016_category_casing", "0016_category_spelling")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
