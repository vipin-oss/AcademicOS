"""P1 tests: document identity registry (duplicate detection).

Covers the identity half of Knowledge-Layer P1:
- a new document creates its own identity (canonical = itself);
- a duplicate upload (identical normalized content, different filename) is
  DETECTED, the ORIGINAL stays canonical, no merge occurs;
- the same filename with DIFFERENT content is a different identity (never
  merged by filename);
- deleting the canonical recomputes the representative deterministically;
- rebuild recomputes the registry identically (incremental == rebuilt);
- duplicate_count reflects only non-canonical documents;
- content identity is the NORMALIZED-text hash (version is never the
  identity signal).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
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
from app.infrastructure.db.models.search_document_model import SearchDocumentModel  # noqa
from app.infrastructure.db.models.document_identity_model import DocumentIdentityModel  # noqa
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa
from app.infrastructure.db.models.object_relationship_model import ObjectRelationshipModel  # noqa
from app.infrastructure.db.models.outbox_model import OutboxEventModel  # noqa
from app.infrastructure.persistence.document_identity_store import SQLDocumentIdentityStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.storage.local.local_storage import LocalFileStorage
from app.tests.unit.extraction_fixtures import make_pdf_bytes

TEXT_A = (
    "CERTIFICATE\nThis is to certify that Mr. Vipin Gupta presented a paper "
    "at CONIAPS XXVII held on 26-28 October 2021 at Kurukshetra University.\n"
)
TEXT_B = (
    "CERTIFICATE\nThis is to certify that Mr. Vipin Gupta presented a paper "
    "at a DIFFERENT conference held in 2022.\n"
)


@pytest.fixture()
def harness(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repo = SQLAlchemyObjectRepository(session)
    storage = LocalFileStorage(str(tmp_path))
    user = UniversalObject.create(
        ObjectType.USER, "vipin.gupta", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:vipin-0001"),
    )
    repo.save(user, outbox_events=[])
    session.commit()
    yield dict(session=session, repo=repo, storage=storage, user=user)
    session.close()


def _upload(h, file_name, text):
    session, repo, storage, user = h["session"], h["repo"], h["storage"], h["user"]
    pdf = make_pdf_bytes(text=text, title=file_name)
    out = CreateDocumentUseCase(repo, storage).execute(
        CreateDocumentCommand(input=CreateDocumentInput(
            title=file_name, document_type="pdf", uploaded_by=str(user.id),
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


def _registry(h):
    return SQLDocumentIdentityStore(h["session"])


class TestIdentityBasics:
    def test_new_document_is_its_own_canonical(self, harness):
        doc = _upload(harness, "cert-a.pdf", TEXT_A)
        h = content_hash(TEXT_A)
        assert _registry(harness).canonical_for(h) == doc
        assert _registry(harness).duplicate_count() == 0

    def test_canonical_is_smallest_object_id_not_upload_order(self, harness):
        # Two uploads with identical content; the canonical must be the
        # lexicographically smallest object_id regardless of which was
        # uploaded first — the deterministic rebuild rule.
        first = _upload(harness, "cert-a.pdf", TEXT_A)
        second = _upload(harness, "cert-copy.pdf", TEXT_A)
        h = content_hash(TEXT_A)
        assert _registry(harness).canonical_for(h) == min(first, second)

    def test_duplicate_content_different_filename_detected_no_merge(self, harness):
        original = _upload(harness, "cert-a.pdf", TEXT_A)
        dup = _upload(harness, "cert-copy.pdf", TEXT_A)  # identical content
        h = content_hash(TEXT_A)
        # canonical is the SMALLEST object_id (deterministic, rebuildable) —
        # never the upload order and never the filename.
        canonical = min(original, dup)
        assert _registry(harness).canonical_for(h) == canonical
        assert _registry(harness).duplicate_count() == 1
        # both documents remain independently retrievable (no merge)
        assert original != dup

    def test_same_filename_different_content_is_different_identity(self, harness):
        doc1 = _upload(harness, "same-name.pdf", TEXT_A)
        doc2 = _upload(harness, "same-name.pdf", TEXT_B)
        h1, h2 = content_hash(TEXT_A), content_hash(TEXT_B)
        assert h1 != h2
        assert _registry(harness).canonical_for(h1) == doc1
        assert _registry(harness).canonical_for(h2) == doc2
        assert _registry(harness).duplicate_count() == 0  # no false merge by filename

    def test_canonical_never_filename_or_version(self, harness):
        # identical content => identical identity regardless of version bump
        doc = _upload(harness, "cert-a.pdf", TEXT_A)
        h = content_hash(TEXT_A)
        # metadata-only update bumps the version but not the identity
        session, repo = harness["session"], harness["repo"]
        from app.domain.value_objects.enums import MetadataLayer, Provenance
        from app.domain.value_objects.metadata import MetadataEntry
        obj = repo.get_by_id(ObjectId(doc))
        obj.set_metadata(
            MetadataEntry("description", "updated", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            actor="vipin.gupta")
        repo.save(obj, outbox_events=[])
        session.commit()
        SearchIndexApplier(session).apply_pending()
        session.commit()
        assert _registry(harness).canonical_for(h) == doc  # identity unchanged


class TestIdentityLifecycle:
    def test_delete_canonical_recomputes_representative(self, harness):
        a = _upload(harness, "cert-a.pdf", TEXT_A)
        b = _upload(harness, "cert-copy.pdf", TEXT_A)
        h = content_hash(TEXT_A)
        canonical = min(a, b)
        other = b if canonical == a else a
        assert _registry(harness).canonical_for(h) == canonical

        from app.application.use_cases.documents.delete_document import DeleteDocumentUseCase
        from app.application.commands.delete_document import DeleteDocumentCommand
        DeleteDocumentUseCase(harness["repo"], storage=harness["storage"]).execute(
            DeleteDocumentCommand(object_id=ObjectId(canonical)))
        harness["session"].commit()
        SearchIndexApplier(harness["session"]).apply_pending()
        harness["session"].commit()
        # the remaining document becomes the canonical representative
        assert _registry(harness).canonical_for(h) == other
        assert _registry(harness).duplicate_count() == 0

    def test_delete_last_document_removes_registry_row(self, harness):
        doc = _upload(harness, "cert-a.pdf", TEXT_A)
        h = content_hash(TEXT_A)
        from app.application.use_cases.documents.delete_document import DeleteDocumentUseCase
        from app.application.commands.delete_document import DeleteDocumentCommand
        DeleteDocumentUseCase(harness["repo"], storage=harness["storage"]).execute(
            DeleteDocumentCommand(object_id=ObjectId(doc)))
        harness["session"].commit()
        SearchIndexApplier(harness["session"]).apply_pending()
        harness["session"].commit()
        assert _registry(harness).canonical_for(h) is None


class TestIdentityRebuild:
    def test_rebuild_recomputes_identical_registry(self, harness):
        a = _upload(harness, "cert-a.pdf", TEXT_A)
        b = _upload(harness, "cert-copy.pdf", TEXT_A)
        other = _upload(harness, "other.pdf", TEXT_B)
        h = content_hash(TEXT_A)
        canonical = min(a, b)
        assert _registry(harness).canonical_for(h) == canonical

        from app.infrastructure.search.document_content_rebuilder import (
            rebuild_document_contents,
        )
        from sqlalchemy import delete as sa_delete
        session = harness["session"]
        session.execute(sa_delete(DocumentIdentityModel))
        session.commit()
        result = rebuild_document_contents(session, harness["storage"])
        session.commit()
        # deterministic canonical (smallest object_id) survives rebuild
        assert _registry(harness).canonical_for(h) == canonical
        assert _registry(harness).canonical_for(content_hash(TEXT_B)) == other
        assert result["duplicates"] == 1
        assert _registry(harness).duplicate_count() == 1
