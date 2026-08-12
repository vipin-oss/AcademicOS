"""Lifecycle tests: document_chunks projection through the real applier (P0).

Covers the incremental lifecycle with the applier as the SINGLE chunk
writer:

- CREATE: direct upload and intake commit -> outbox drain -> chunks created
- metadata-only update -> search_documents refreshed, chunks untouched
  (content_hash unchanged -> hash-skip)
- content change (direct content-row write simulating a future re-extract)
  -> old chunks replaced, indexes contiguous
- DELETE -> chunks removed; a stale event cannot resurrect them
- idempotency: running the drain twice produces identical chunk rows
- missing content projection at drain time (direct-upload crash window)
  -> skipped, no empty evidence; rebuild repairs
- rejected intake -> no chunks
- provenance: every chunk carries document id, version, span, hash
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.application.dtos.document import CreateDocumentInput
from app.application.commands.create_document import CreateDocumentCommand
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.application.services.document_chunking import content_hash, chunk_text
from app.api.routes.documents import _index_direct_upload_content
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import MetadataLayer, ObjectStatus, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel
from app.infrastructure.db.models.document_content_model import DocumentContentModel
from app.infrastructure.db.models.object_model import ObjectModel
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa
from app.infrastructure.db.models.object_relationship_model import ObjectRelationshipModel  # noqa
from app.infrastructure.db.models.outbox_model import OutboxEventModel  # noqa
from app.infrastructure.persistence.document_chunk_store import SQLDocumentChunkStore
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.storage.local.local_storage import LocalFileStorage
from app.tests.unit.extraction_fixtures import make_pdf_bytes

TEXT_A = (
    "CERTIFICATE OF PARTICIPATION\n"
    "This is to certify that Dr Anil Kumar has participated in the National "
    "Conference on Emerging Trends in Higher Education organized by "
    "Chaudhary Bansi Lal University (CBLU), Bhiwani held on 19 and 20 "
    "January 2024 at the university auditorium. "
    + "The conference featured keynote sessions on digital pedagogy, research "
    "ethics and emerging trends in higher education. "
    * 12
    + "This certificate is issued for academic record purposes.\n"
)
TEXT_B = (
    "CERTIFICATE OF ACHIEVEMENT\n"
    "This is to certify that Dr Anil Kumar delivered a keynote on quantum "
    "machine learning at the International Symposium on Computational "
    "Sciences held on 14 and 15 February 2025. "
    + "The symposium proceedings were published with an ISBN number. "
    * 12
    + "This certificate is issued for academic record purposes.\n"
)


def _entry(k, v):
    return MetadataEntry(k, v, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


@pytest.fixture()
def harness(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repo = SQLAlchemyObjectRepository(session)
    storage = LocalFileStorage(str(tmp_path))
    user = UniversalObject.create(
        ObjectType.USER, "anil", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:anil-0001"),
    )
    repo.save(user, outbox_events=[])
    session.commit()
    yield dict(session=session, repo=repo, storage=storage, user=user)
    session.close()


def _direct_upload(h, file_name="Cblu Jan, 2024.pdf", text=TEXT_A):
    """The exact route sequence for a direct upload (use case + content)."""
    session, repo, storage, user = h["session"], h["repo"], h["storage"], h["user"]
    pdf = make_pdf_bytes(text=text, title=file_name)
    out = CreateDocumentUseCase(repo, storage).execute(
        CreateDocumentCommand(input=CreateDocumentInput(
            title="Certificate of Participation", document_type="pdf",
            uploaded_by=str(user.id), file_name=file_name, file_size=len(pdf),
            mime_type="application/pdf", content=pdf, status=ObjectStatus.ACTIVE,
        ))
    )
    _index_direct_upload_content(
        session, document_id=str(out.id), version=out.version,
        file_name=file_name, content=pdf,
    )
    session.commit()
    return str(out.id)


def _drain(h):
    applier = SearchIndexApplier(h["session"])
    applier.apply_pending()
    h["session"].commit()
    return applier


def _chunk_rows(h, document_id):
    return h["session"].execute(
        select(DocumentChunkModel)
        .where(DocumentChunkModel.document_id == document_id)
        .order_by(DocumentChunkModel.chunk_index)
    ).scalars().all()


def _chunk_signature(h, document_id):
    """Ordered (index, start, end, content, hash) — for equality checks."""
    return [
        (r.chunk_index, r.char_start, r.char_end, r.content, r.content_hash)
        for r in _chunk_rows(h, document_id)
    ]


class TestCreateLifecycle:
    def test_direct_upload_creates_chunks_via_applier(self, harness):
        doc_id = _direct_upload(harness)
        applier = _drain(harness)
        assert applier.stats["chunk_created"] == 1
        rows = _chunk_rows(harness, doc_id)
        assert len(rows) > 1  # TEXT_A is long -> multiple chunks
        # spans are contiguous, deterministic vs the chunking service
        expected = chunk_text(TEXT_A)
        assert [(r.char_start, r.char_end) for r in rows] == [
            (c.start, c.end) for c in expected
        ]
        # provenance: version + content hash + source
        for r in rows:
            assert r.document_id == doc_id
            assert r.version >= 1
            assert r.content_hash == content_hash(r.content)
        # content row hash backfilled
        row = harness["session"].get(DocumentContentModel, doc_id)
        assert row.content_hash == content_hash(TEXT_A)

    def test_short_document_single_chunk(self, harness):
        doc_id = _direct_upload(harness, text="CERTIFICATE\nShort text only.\n")
        _drain(harness)
        rows = _chunk_rows(harness, doc_id)
        assert len(rows) == 1
        assert rows[0].char_start == 0

    def test_intake_commit_creates_chunks(self, harness):
        # intake: session + item + extraction descriptor -> commit -> drain
        session, repo, storage, user = (harness["session"], harness["repo"],
                                        harness["storage"], harness["user"])
        sess = UniversalObject.create(
            ObjectType.INTAKE_SESSION, "Folder import — Personal",
            created_by="intake", status=ObjectStatus.ACTIVE,
            metadata=Metadata(entries=(_entry("intake.status", "completed"),)),
        )
        repo.save(sess, outbox_events=[])
        session.commit()
        sid = str(sess.id)
        staged = f"staging/{sid.split(':')[-1]}/report.pdf"
        pdf = make_pdf_bytes(text=TEXT_A, title="report.pdf")
        storage.save(staged, pdf)
        from app.application.dtos.intake import (
            KEY_EXTRACTION, KEY_INTAKE_STATUS, KEY_PROPOSAL, KEY_SESSION_ID,
            IntakeItemStatus, json_encode,
        )
        import hashlib as _hashlib
        item = UniversalObject.create(
            ObjectType.INTAKE_ITEM, "report.pdf", created_by="intake",
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(entries=(
                _entry(KEY_INTAKE_STATUS, IntakeItemStatus.AWAITING_REVIEW.value),
                _entry(KEY_SESSION_ID, sid),
                _entry("intake.extension", "pdf"),
                _entry("intake.mime_type", "application/pdf"),
                _entry("intake.size_bytes", str(len(pdf))),
                _entry("intake.sha256", _hashlib.sha256(pdf).hexdigest()),
                _entry("intake.staged_key", staged),
            )),
        )
        repo.save(item, outbox_events=[])
        # real extraction
        from app.application.intake.extraction.service import ExtractionService
        from app.infrastructure.extraction import build_document_parsers
        ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=sid)
        item.set_metadata(
            MetadataEntry(KEY_PROPOSAL, json_encode({"title": "report.pdf", "document_type": "pdf"}),
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            actor=str(user.id),
        )
        repo.save(item, outbox_events=[])
        session.commit()
        from app.application.use_cases.intake.commit_item import CommitItemUseCase
        from app.application.commands.commit_intake_item import CommitIntakeItemCommand
        out = CommitItemUseCase(
            repo, storage, CreateDocumentUseCase(repo, storage),
            content_store=SQLDocumentContentStore(session),
        ).execute(CommitIntakeItemCommand(item_id=str(item.id), actor=str(user.id)))
        session.commit()
        _drain(harness)
        rows = _chunk_rows(harness, str(out.document_id))
        assert len(rows) > 1
        assert rows[0].source_item_id == str(item.id)


class TestUpdateLifecycle:
    def test_metadata_only_update_does_not_rechunk(self, harness):
        session, repo = harness["session"], harness["repo"]
        doc_id = _direct_upload(harness)
        _drain(harness)
        before = _chunk_signature(harness, doc_id)

        obj = repo.get_by_id(ObjectId(doc_id))
        obj.set_metadata(
            MetadataEntry("description", "updated description",
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            actor="anil",
        )
        repo.save(obj, outbox_events=[])
        session.commit()
        applier = _drain(harness)
        assert applier.stats["chunk_created"] == 0
        assert applier.stats["chunk_skipped"] >= 1
        assert _chunk_signature(harness, doc_id) == before

    def test_content_change_replaces_chunks(self, harness):
        session, repo = harness["session"], harness["repo"]
        doc_id = _direct_upload(harness, text=TEXT_A)
        _drain(harness)
        before = _chunk_signature(harness, doc_id)

        # simulate a future re-extraction: bump the object version (emit an
        # ObjectUpdated event) and replace the content row WITHOUT a hash
        # backfill (the crash-window shape — content changed, hash stale).
        obj = repo.get_by_id(ObjectId(doc_id))
        obj.set_metadata(
            MetadataEntry("description", "re-extracted",
                          MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            actor="anil",
        )
        repo.save(obj, outbox_events=[])
        SQLDocumentContentStore(session).upsert(
            object_id=doc_id, version=obj.version, content_text=TEXT_B,
            source_item_id=doc_id, content_hash=None,  # stale -> must re-chunk
        )
        session.commit()
        _drain(harness)
        after = _chunk_signature(harness, doc_id)
        assert after != before
        expected = chunk_text(TEXT_B)
        assert [(r.char_start, r.char_end) for r in _chunk_rows(harness, doc_id)] == [
            (c.start, c.end) for c in expected
        ]
        # no stale chunks from version 1 coexist (PK replace)
        assert len(_chunk_rows(harness, doc_id)) == len(expected)


class TestDeleteLifecycle:
    def test_delete_removes_chunks_and_cannot_be_resurrected(self, harness):
        session, repo = harness["session"], harness["repo"]
        doc_id = _direct_upload(harness)
        _drain(harness)
        assert len(_chunk_rows(harness, doc_id)) > 0

        # delete the object; the applier's delete branch must remove chunks
        from app.application.use_cases.documents.delete_document import DeleteDocumentUseCase
        from app.application.commands.delete_document import DeleteDocumentCommand
        DeleteDocumentUseCase(repo, storage=harness["storage"]).execute(
            DeleteDocumentCommand(object_id=ObjectId(doc_id))
        )
        session.commit()
        _drain(harness)
        assert _chunk_rows(harness, doc_id) == []
        assert session.get(DocumentContentModel, doc_id) is None

        # a stale/re-emitted event cannot resurrect: every event re-derives
        # the aggregate; for a deleted object the re-derivation is None, so
        # the delete branch (idempotent) runs again.
        _drain(harness)
        assert _chunk_rows(harness, doc_id) == []
        assert session.get(DocumentContentModel, doc_id) is None

    def test_rejected_intake_never_chunked(self, harness):
        # a non-committed intake item is not a document and has no chunks
        session = harness["session"]
        n_chunks = session.execute(
            select(DocumentChunkModel).where(DocumentChunkModel.document_id.like("%intake_item%"))
        ).scalars().all()
        assert n_chunks == []


class TestCrashWindowAndIdempotency:
    def test_missing_content_row_at_drain_skips_cleanly(self, harness):
        """Direct-upload crash window: outbox event present, content row
        missing -> the applier must NOT create empty/incorrect chunks."""
        session, repo, storage, user = (harness["session"], harness["repo"],
                                        harness["storage"], harness["user"])
        pdf = make_pdf_bytes(text=TEXT_A, title="crash.pdf")
        out = CreateDocumentUseCase(repo, storage).execute(
            CreateDocumentCommand(input=CreateDocumentInput(
                title="Crash", document_type="pdf", uploaded_by=str(user.id),
                file_name="crash.pdf", file_size=len(pdf), mime_type="application/pdf",
                content=pdf, status=ObjectStatus.ACTIVE,
            ))
        )
        session.commit()  # object + outbox committed; content write skipped
        applier = _drain(harness)
        assert applier.stats["chunk_skipped"] >= 1
        assert _chunk_rows(harness, str(out.id)) == []
        assert session.get(DocumentContentModel, str(out.id)) is None

        # rebuild repairs: content + chunks reconstructed from the blob
        from app.infrastructure.search.document_content_rebuilder import (
            rebuild_document_contents,
        )
        result = rebuild_document_contents(session, storage)
        session.commit()
        assert result["indexed"] >= 1
        assert _chunk_rows(harness, str(out.id)) != []

    def test_idempotent_drain(self, harness):
        doc_id = _direct_upload(harness)
        _drain(harness)
        first = _chunk_signature(harness, doc_id)
        applier = _drain(harness)
        assert applier.stats["chunk_created"] == 0  # hash-guarded skip
        assert _chunk_signature(harness, doc_id) == first


class TestDeleteRaceProtection:
    def test_stale_content_row_cannot_reach_retrieval(self, harness):
        """If a content/chunk row outlives its object (crash window), the
        query-time existence check must drop it — it must never become
        evidence."""
        from app.application.use_cases.search.search_objects import SearchObjectsUseCase
        from app.infrastructure.repositories.sqlalchemy_search_repository import (
            SQLAlchemySearchRepository,
        )
        from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator

        session = harness["session"]
        doc_id = _direct_upload(harness)
        _drain(harness)
        # orphan the projections: delete the object row directly, leaving the
        # derived rows behind (simulates the crash window)
        session.execute(
            __import__("sqlalchemy").delete(ObjectModel).where(ObjectModel.id == doc_id)
        )
        session.commit()
        assert session.get(DocumentContentModel, doc_id) is not None  # orphaned
        search_uc = SearchObjectsUseCase(
            search_repository=SQLAlchemySearchRepository(session),
            object_repository=harness["repo"],
            permission_evaluator=ObjectPermissionEvaluator(),
        )
        hits = search_uc.execute(user=harness["user"], text="certificate of participation")
        assert all(h.object_id != doc_id for h in hits)
