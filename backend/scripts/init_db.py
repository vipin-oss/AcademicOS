"""Zero-friction database initialiser (SQLite quickstart).

Creates every table from the ORM models and stamps the alembic version
so the schema matches a migrated PostgreSQL database. Intended for the
SQLite quickstart path (``DATABASE_URL=sqlite:///...``), where the
alembic chain itself cannot run because migration 0001 uses
PostgreSQL-only JSONB types.

Usage:
    DATABASE_URL=sqlite:///./academicos.db python scripts/init_db.py

The script is idempotent: an existing database is left untouched when
the alembic stamp is already present.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the backend package importable when the script runs from anywhere
# (``python scripts/init_db.py`` from backend/, or ``python backend/scripts/
# init_db.py`` from the repo root).
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import sqlalchemy as sa

# Register every table before ``Base.metadata.create_all``.
from app.infrastructure.db.models.annotation_model import (  # noqa: F401
    DocumentAnnotationModel,
)
from app.infrastructure.db.models.eval_run_model import EvalRunModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_relationship_model import (  # noqa: F401
    ObjectRelationshipModel,
)
from app.infrastructure.db.models.object_version_model import (  # noqa: F401
    ObjectVersionModel,
)
from app.infrastructure.db.models.outbox_model import OutboxEventModel  # noqa: F401
from app.infrastructure.db.models.review_decision_model import (  # noqa: F401
    ReviewDecisionModel,
)
from app.infrastructure.db.models.search_document_model import (  # noqa: F401
    SearchDocumentModel,
)

CURRENT_MIGRATION = "0008_document_annotations"


def main() -> None:
    url = os.environ.get("DATABASE_URL", "sqlite:///./academicos.db")
    engine = sa.create_engine(url)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
        )
        stamped = conn.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).fetchone()
        if stamped is None:
            conn.execute(
                sa.text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
                {"v": CURRENT_MIGRATION},
            )
            print(f"Schema created and stamped at {CURRENT_MIGRATION}.")
        else:
            print(f"Database already initialised (stamped {stamped[0]}); nothing to do.")
    engine.dispose()


if __name__ == "__main__":
    main()
