"""P1 integration tests: scale & identity projections end-to-end.

- FTS projection is maintained incrementally and rebuilt equivalently;
- a deleted document never reappears through the FTS/content leg
  (stale-event safety);
- ACL filtering applies to FTS-derived candidates (denied user blocked);
- the document registry survives a full rebuild identically;
- chunk lifecycle is untouched by the new projections.
"""
from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import create_engine, delete as sa_delete
from sqlalchemy.orm import sessionmaker

from app.application.services.document_chunking import content_hash
from app.application.dtos.document import CreateDocumentInput
from app.application.commands.create_document import CreateDocumentCommand
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.api.routes.documents import _index_direct_upload_content
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.document_content_model import DocumentContentModel  # noqa
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel  # noqa
from app.infrastructure.db.models.document_identity_model import DocumentIdentityModel  # noqa
from app.infrastructure.db.models.search_document_model import SearchDocumentModel  # noqa
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa
from app.infrastructure.db.models.object_relationship_model import ObjectRelationshipModel  # noqa
from app.infrastructure.db.models.outbox_model import OutboxEventModel  # noqa
from app.infrastructure.persistence.document_identity_store import SQLDocumentIdentityStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.fts import SQLFTSRepository, ensure_fts_schema
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.search.document_content_rebuilder import rebuild_document_contents
from app.infrastructure.storage.local.local_storage import LocalFileStorage
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.application.use_cases.object_acl import update_object_acl
from app.tests.unit.extraction_fixtures import make_pdf_bytes

TEXT_A = (
    "CERTIFICATE\nThis is to certify that Mr. Vipin Gupta presented a paper "
    "at CONIAPS XXVII held on 26-28 October 2021 at Kurukshetra University. "
    "The paper concerned wave propagation in homogenous solids. "
    * 4
    + "End of certificate.\n"
)
TEXT_B = (
    "NOTICE\nThe Academic Council meeting is postponed to 22 February 2025. "
    "All members are requested to note the revised schedule. "
    * 4
    + "Issued by the Office of the Registrar.\n"
)


@pytest.fixture()
def harness(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    ensure_fts_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repo = SQLAlchemyObjectRepository(session)
    storage = LocalFileStorage(str(tmp_path))
    alice = UniversalObject.create(
        ObjectType.USER, "alice", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:alice-0001"),
    )
    bob = UniversalObject.create(
        ObjectType.USER, "bob", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:bob-0002"),
    )
    repo.save(alice, outbox_events=[])
    repo.save(bob, outbox_events=[])
    session.commit()
    yield dict(session=session, repo=repo, storage=storage, alice=alice, bob=bob)
    session.close()


def _upload(h, file_name, text, actor):
    session, repo, storage = h["session"], h["repo"], h["storage"]
    pdf = make_pdf_bytes(text=text, title=file_name)
    out = CreateDocumentUseCase(repo, storage).execute(
        CreateDocumentCommand(input=CreateDocumentInput(
            title=file_name, document_type="pdf", uploaded_by=str(actor.id),
            file_name=file_name, file_size=len(pdf), mime_type="application/pdf",
            content=pdf, status=ObjectStatus.ACTIVE,
        ))
    )
    session.commit()
    _index_direct_upload_content(session, document_id=str(out.id), version=out.version,
                                 file_name=file_name, content=pdf)
    session.commit()
    SearchIndexApplier(session).apply_pending()
    session.commit()
    return str(out.id)


def _search_ids(h, text, user, limit=8):
    session, repo = h["session"], h["repo"]
    search_uc = SearchObjectsUseCase(
        search_repository=SQLAlchemySearchRepository(session), object_repository=repo,
        permission_evaluator=ObjectPermissionEvaluator(),
    )
    return [hit.object_id for hit in search_uc.execute(user=user, text=text, limit=limit)]


class TestFTSLifecycle:
    def test_fts_finds_documents(self, harness):
        doc = _upload(harness, "cert.pdf", TEXT_A, harness["alice"])
        assert doc in _search_ids(harness, "vipin", harness["alice"])
        assert doc in _search_ids(harness, "wave propagation", harness["alice"])
        assert _search_ids(harness, "zebraquirkzz", harness["alice"]) == []

    def test_delete_never_reappears_through_fts(self, harness):
        doc = _upload(harness, "cert.pdf", TEXT_A, harness["alice"])
        assert doc in _search_ids(harness, "vipin", harness["alice"])
        from app.application.use_cases.documents.delete_document import DeleteDocumentUseCase
        from app.application.commands.delete_document import DeleteDocumentCommand
        DeleteDocumentUseCase(harness["repo"], storage=harness["storage"]).execute(
            DeleteDocumentCommand(object_id=ObjectId(doc)))
        harness["session"].commit()
        SearchIndexApplier(harness["session"]).apply_pending()
        harness["session"].commit()
        # gone from FTS + content leg + registry
        assert doc not in _search_ids(harness, "vipin", harness["alice"])
        assert SQLFTSRepository(harness["session"]).search("vipin", limit=10) == []
        # a stale re-drain cannot resurrect it (re-derivation is None)
        SearchIndexApplier(harness["session"]).apply_pending()
        harness["session"].commit()
        assert doc not in _search_ids(harness, "vipin", harness["alice"])

    def test_acl_denied_user_blocked_on_fts_path(self, harness):
        doc = _upload(harness, "private.pdf", TEXT_A, harness["alice"])
        # restrict to alice
        update_object_acl(harness["repo"], doc, {
            "readers": [str(harness["alice"].id)], "writers": [str(harness["alice"].id)],
            "managers": [str(harness["alice"].id)],
        })
        assert doc in _search_ids(harness, "vipin", harness["alice"])
        assert doc not in _search_ids(harness, "vipin", harness["bob"])


class TestRebuildEquivalence:
    def test_fts_and_registry_equivalent_after_rebuild(self, harness):
        a = _upload(harness, "cert-a.pdf", TEXT_A, harness["alice"])
        b = _upload(harness, "cert-copy.pdf", TEXT_A, harness["alice"])  # duplicate
        c = _upload(harness, "notice.pdf", TEXT_B, harness["alice"])
        h = content_hash(TEXT_A)
        canonical = min(a, b)

        def fts_ids(term):
            return [oid for oid, _ in SQLFTSRepository(harness["session"]).search(term, limit=20)]

        inc_fts = fts_ids("vipin") + fts_ids("notice")
        inc_canonical = SQLDocumentIdentityStore(harness["session"]).canonical_for(h)

        # wipe ALL derived projections (search + content + chunks + fts +
        # registry) and rebuild from source of truth
        session = harness["session"]
        from app.infrastructure.db.models.search_document_model import SearchDocumentModel as SDM
        session.execute(sa_delete(SDM))
        session.execute(sa_delete(DocumentContentModel))
        session.execute(sa_delete(DocumentChunkModel))
        session.execute(sa_delete(DocumentIdentityModel))
        session.execute(sa_delete(__import__("app.infrastructure.db.models.outbox_model", fromlist=["OutboxEventModel"]).OutboxEventModel))
        session.commit()
        SearchIndexApplier(session).rebuild()
        session.commit()
        rebuild_document_contents(session, harness["storage"])
        session.commit()
        # re-drain for any remaining events (idempotent)
        SearchIndexApplier(session).apply_pending()
        session.commit()

        reb_fts = fts_ids("vipin") + fts_ids("notice")
        reb_canonical = SQLDocumentIdentityStore(harness["session"]).canonical_for(h)
        assert sorted(inc_fts) == sorted(reb_fts)
        assert inc_canonical == reb_canonical == canonical

    def test_chunk_lifecycle_intact_with_new_projections(self, harness):
        doc = _upload(harness, "cert.pdf", TEXT_A, harness["alice"])
        rows = harness["session"].execute(
            __import__("sqlalchemy").select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == doc)
            .order_by(DocumentChunkModel.chunk_index)
        ).scalars().all()
        assert len(rows) >= 1
        # chunk spans deterministic
        from app.application.services.document_chunking import chunk_text
        expected = chunk_text(TEXT_A)
        assert [(r.char_start, r.char_end) for r in rows] == [
            (c.start, c.end) for c in expected
        ]
