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
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.db.models.cdm_decision_model import CdmDecisionModel  # noqa: F401
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_decision_model import ClaimDecisionModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.document_content_model import (  # noqa: F401
    DocumentContentModel,
)
from app.infrastructure.db.models.document_chunk_model import (  # noqa: F401
    DocumentChunkModel,
)
from app.infrastructure.db.models.document_identity_model import (  # noqa: F401
    DocumentIdentityModel,
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
from app.infrastructure.db.models.tool_call_log_model import (  # noqa: F401
    ToolCallLogModel,
)
from app.infrastructure.db.models.session_revocation_model import (  # noqa: F401
    SessionRevocationModel,
)
from app.infrastructure.db.models.document_revision_model import (  # noqa: F401
    DocumentRevisionModel,
)
from app.infrastructure.db.models.job_model import (  # noqa: F401
    JobAttemptModel,
    JobModel,
)
from app.infrastructure.db.models.accreditation_model import (  # noqa: F401
    AccreditationSubmissionModel,
)
from app.infrastructure.db.models.user_profile_model import (  # noqa: F401
    UserProfileModel,
)
from app.infrastructure.db.models.organization_model import (  # noqa: F401
    MembershipModel,
    OrganizationModel,
)
from app.infrastructure.db.models.saved_view_model import (  # noqa: F401
    SavedViewModel,
)
from app.infrastructure.db.models.spend_ledger_model import (  # noqa: F401
    SpendLedgerModel,
)
from app.infrastructure.db.models.notification_model import NotificationModel  # noqa: F401
from app.infrastructure.db.models.entity_match_model import EntityMatchModel  # noqa: F401


CURRENT_MIGRATION = "0027_entity_matches"


def main() -> None:
    url = os.environ.get("DATABASE_URL", "sqlite:///./academicos.db")
    engine = sa.create_engine(url)
    Base.metadata.create_all(engine)
    # P1: the full-text search projection (FTS5 virtual table on SQLite;
    # PostgreSQL gets the same schema via alembic 0011).
    from app.infrastructure.search.fts import ensure_fts_schema

    ensure_fts_schema(engine)
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
