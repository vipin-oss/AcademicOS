"""V3 M3 — tenancy stamping (columns only, no enforcement).

Verifies the M3 contract (blueprint §M3, audit A7):

- every one of the 18 tables (17 ORM + ``document_search_fts``) carries
  ``tenant_id`` + ``owner_user_id``;
- both are ``NOT NULL DEFAULT 'default'`` — so no write path can produce a NULL
  and post-backfill ``tenant_id`` is NULL-free by construction;
- ``document_chunks`` keeps its composite PK ``(document_id, chunk_index)`` —
  a tenancy partition key does not belong in that PK (enforcement is M9);
- the FTS upsert and the object repository both stamp ``'default'`` without any
  caller change;
- migration 0015 chains off 0014 (the single migration chain is preserved).

No enforcement here: reads remain open (M9 flips them).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# Register every table on Base.metadata (same explicit list as init_db.py).
from app.infrastructure.db.models.annotation_model import (  # noqa: F401
    DocumentAnnotationModel,
)
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.db.models.cdm_decision_model import CdmDecisionModel  # noqa: F401
from app.infrastructure.db.models.claim_decision_model import ClaimDecisionModel  # noqa: F401
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel  # noqa: F401
from app.infrastructure.db.models.document_content_model import (  # noqa: F401
    DocumentContentModel,
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

REPO = Path(__file__).resolve().parents[4]

EXPECTED_TABLES = {
    "cdm_blocks",
    "cdm_decisions",
    "claim_decisions",
    "claim_spans",
    "claims",
    "document_annotations",
    "document_chunks",
    "document_contents",
    "document_registry",
    "eval_runs",
    "object_relationships",
    "object_versions",
    "objects",
    "outbox_events",
    "review_decisions",
    "search_documents",
    "tool_call_log",
}


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    from app.infrastructure.search.fts import ensure_fts_schema

    ensure_fts_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_all_orm_tables_stamped() -> None:
    # The M3 set (17 tables) has grown additively (M9 session_revocations,
    # M10 jobs/job_attempts); every table — old or new — must carry the stamp.
    assert EXPECTED_TABLES <= set(Base.metadata.tables)
    for table in Base.metadata.tables.values():
        cols = table.columns
        assert "tenant_id" in cols, table.name
        assert "owner_user_id" in cols, table.name
        tenant = cols["tenant_id"]
        owner = cols["owner_user_id"]
        assert not tenant.nullable and tenant.server_default is not None, table.name
        assert not owner.nullable and owner.server_default is not None, table.name


def test_tenant_columns_are_indexed() -> None:
    for table in Base.metadata.tables.values():
        names = {ix.name for ix in table.indexes}
        assert f"ix_{table.name}_tenant_id" in names, table.name
        assert f"ix_{table.name}_owner_user_id" in names, table.name


def test_document_chunks_composite_pk_unchanged() -> None:
    pk = [c.name for c in Base.metadata.tables["document_chunks"].primary_key]
    assert pk == ["document_id", "chunk_index"]


def test_fts_table_stamped_and_upsert_writes_defaults(db) -> None:
    from app.infrastructure.search.fts import SQLFTSRepository

    fts = SQLFTSRepository(db)
    fts.upsert(
        object_id="obj:document:m3", object_type="document", version=1,
        title="M3 tenancy", metadata_text="", content_text="stamp", chunks_text="",
    )
    db.commit()

    columns = {c["name"] for c in inspect(db.get_bind()).get_columns("document_search_fts")}
    assert {"tenant_id", "owner_user_id"} <= columns

    # FTS5 virtual tables expose their UNINDEXED metadata columns to direct
    # SELECT; assert the upsert stamped the defaults.
    row = db.execute(
        sqlalchemy.text(
            "SELECT tenant_id, owner_user_id FROM document_search_fts "
            "WHERE object_id = 'obj:document:m3'"
        )
    ).fetchone()
    assert row is not None and row[0] == "default" and row[1] == "default"


def test_object_save_stamps_defaults(db) -> None:
    from app.domain.entities.object import UniversalObject
    from app.domain.value_objects.enums import ObjectStatus, ObjectType
    from app.domain.value_objects.object_id import ObjectId
    from app.infrastructure.repositories.sqlalchemy_object_repository import (
        SQLAlchemyObjectRepository,
    )

    obj = UniversalObject.create(
        ObjectType.DOCUMENT, "M3 Doc", created_by="u:1", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:document:m3save"),
    )
    SQLAlchemyObjectRepository(db).save(obj)

    row = db.execute(
        sqlalchemy.text(
            "SELECT tenant_id, owner_user_id FROM objects WHERE id = 'obj:document:m3save'"
        )
    ).fetchone()
    assert row is not None and row[0] == "default" and row[1] == "default"


def test_migration_0015_chains_off_0014() -> None:
    mig = (
        REPO / "backend" / "alembic" / "versions" / "0015_tenancy_stamping.py"
    )
    text = mig.read_text(encoding="utf-8")
    assert 'revision = "0015_tenancy_stamping"' in text
    assert 'down_revision = "0014_tool_call_log"' in text
    assert "document_chunks" in text  # the composite-PK table is named explicitly


def test_init_db_stamp_tracks_migration_head() -> None:
    # init_db.py stamps the CURRENT migration head (0015 at M3; later milestones
    # advance it — e.g. 0016 typed claims at M5). Assert it points at a real
    # migration file rather than pinning a specific number.
    text = (REPO / "backend" / "scripts" / "init_db.py").read_text(encoding="utf-8")
    import re

    match = re.search(r'CURRENT_MIGRATION = "([0-9a-z_]+)"', text)
    assert match is not None, "init_db.py must stamp a migration revision"
    revision = match.group(1)
    versions = REPO / "backend" / "alembic" / "versions"
    assert any(p.name.startswith(revision) for p in versions.glob("*.py")), revision
