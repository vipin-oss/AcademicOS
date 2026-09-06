"""objects.search_year — materialized year column for SQL-pushdown filters (P1)

Revision ID: 0028_search_year
Revises: 0027
Create Date: 2026-09-06

2026-09 audit follow-up (P1): year-filtered listings (e.g. "conferences in
2024") previously loaded every row of an object type and filtered in
Python — measured 46x slower than the SQL-paginated plain listing at just
6,000 rows, growing linearly and unboundedly with dataset size. This adds
a nullable, indexed ``search_year`` column to ``objects``, populated by
the repository's ``save()`` for object types with a registered date
source key (starting with EVENT — see ``_SEARCH_YEAR_SOURCE_KEY`` in
``sqlalchemy_object_repository.py``). Additive and backward compatible:
existing rows get NULL until next save, which the query layer treats as
"not eligible for the fast path" rather than a data-loss risk — those
rows remain reachable via the pre-existing Python-filtered path.

A follow-up backfill (out of scope here) should walk existing EVENT rows
once to populate search_year from their stored start_date, so the fast
path covers pre-migration data immediately rather than waiting for the
next edit to each row.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0028_search_year"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("objects", sa.Column("search_year", sa.Integer(), nullable=True))
    op.create_index("ix_objects_search_year", "objects", ["search_year"])


def downgrade() -> None:
    op.drop_index("ix_objects_search_year", table_name="objects")
    op.drop_column("objects", "search_year")
