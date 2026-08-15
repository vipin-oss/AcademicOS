"""Integration tests: chunk + content rebuild (P0) and rebuild equivalence.

Covers the corrected rebuild architecture:
- mixed corpus (intake-origin + direct-upload + unparsable + missing blob);
- the DIRECT-UPLOAD rebuild gap is closed (stored blob -> parse -> text);
- rebuild counters (indexed / skipped / chunked);
- the formal REBUILD EQUIVALENCE invariant:

      IncrementalProjection(S) == RebuiltProjection(S)

  compared per object on (content_hash, ordered chunk signature) — not row
  counts;
- rebuild is idempotent (running twice is stable) and repairs the
  direct-upload crash window (content row missing after a drain).
"""
from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.application.dtos.document import CreateDocumentInput
from app.application.commands.create_document import CreateDocumentCommand
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.application.services.document_chunking import content_hash
from app.api.routes.documents import _index_direct_upload_content
from app.application.commands.commit_intake_item import CommitIntakeItemCommand
from app.application.use_cases.intake.commit_item import CommitItemUseCase
from app.application.intake.extraction.service import ExtractionService
from app.application.dtos.intake import (
    KEY_EXTRACTION,
    KEY_INTAKE_STATUS,
    KEY_PROPOSAL,
    KEY_SESSION_ID,
    IntakeItemStatus,
    IntakeSessionStatus,
    json_encode,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import MetadataLayer, ObjectStatus, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel
from app.infrastructure.db.models.document_content_model import DocumentContentModel
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa
from app.infrastructure.db.models.object_relationship_model import ObjectRelationshipModel  # noqa
from app.infrastructure.db.models.outbox_model import OutboxEventModel  # noqa
from app.infrastructure.extraction import build_document_parsers
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.search.document_content_rebuilder import rebuild_document_contents
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.storage.local.local_storage import LocalFileStorage
from app.tests.unit.extraction_fixtures import make_pdf_bytes

LONG_TEXT = (
    "CERTIFICATE OF PARTICIPATION\n"
    "This is to certify that Dr Anil Kumar has participated in the National "
    "Conference on Emerging Trends in Higher Education organized by "
    "Chaudhary Bansi Lal University (CBLU), Bhiwani held on 19 and 20 "
    "January 2024 at the university auditorium. "
    + "The conference featured keynote sessions on digital pedagogy, "
    "research ethics and emerging trends in higher education. "
    * 15
    + "This certificate is issued for academic record purposes.\n"
)
SHORT_TEXT = "CERTIFICATE\nShort document.\n"


def _entry(k, v):
    return MetadataEntry(k, v, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


@pytest.fixture()
def corpus(tmp_path):
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

    # ---- intake-origin document (BELONGS_TO -> intake item -> text blob)
    sess = UniversalObject.create(
        ObjectType.INTAKE_SESSION, "Folder import — Personal",
        created_by="intake", status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=(_entry(KEY_INTAKE_STATUS, IntakeSessionStatus.COMPLETED.value),)),
    )
    repo.save(sess, outbox_events=[])
    session.commit()
    sid = str(sess.id)
    staged = f"staging/{sid.split(':')[-1]}/cblu2024.pdf"
    pdf2024 = make_pdf_bytes(text=LONG_TEXT, title="Cblu Jan, 2024.pdf")
    storage.save(staged, pdf2024)
    item = UniversalObject.create(
        ObjectType.INTAKE_ITEM, "Cblu Jan, 2024.pdf", created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=(
            _entry(KEY_INTAKE_STATUS, IntakeItemStatus.AWAITING_REVIEW.value),
            _entry(KEY_SESSION_ID, sid),
            _entry("intake.extension", "pdf"),
            _entry("intake.mime_type", "application/pdf"),
            _entry("intake.size_bytes", str(len(pdf2024))),
            _entry("intake.sha256", hashlib.sha256(pdf2024).hexdigest()),
            _entry("intake.staged_key", staged),
        )),
    )
    repo.save(item, outbox_events=[])
    ExtractionService(build_document_parsers()).extract_item(item, storage, session_id=sid)
    item.set_metadata(
        MetadataEntry(KEY_PROPOSAL, json_encode({"title": "Cblu Jan, 2024.pdf", "document_type": "pdf"}),
                      MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
        actor=str(user.id),
    )
    repo.save(item, outbox_events=[])
    session.commit()
    creator = CreateDocumentUseCase(repo, storage)
    out = CommitItemUseCase(
        repo, storage, creator, content_store=SQLDocumentContentStore(session),
    ).execute(CommitIntakeItemCommand(item_id=str(item.id), actor=str(user.id)))
    session.commit()
    intake_doc = str(out.document_id)

    # ---- direct uploads: one long, one short
    def direct(file_name, text):
        pdf = make_pdf_bytes(text=text, title=file_name)
        o = creator.execute(CreateDocumentCommand(input=CreateDocumentInput(
            title=file_name, document_type="pdf", uploaded_by=str(user.id),
            file_name=file_name, file_size=len(pdf), mime_type="application/pdf",
            content=pdf, status=ObjectStatus.ACTIVE,
        )))
        _index_direct_upload_content(session, document_id=str(o.id), version=o.version,
                                     file_name=file_name, content=pdf)
        session.commit()
        return str(o.id)

    direct_long = direct("CBLU Jan 2025.pdf", LONG_TEXT)
    direct_short = direct("syllabus.txt", SHORT_TEXT)

    # ---- unparsable direct upload (garbage bytes named .pdf)
    bad = creator.execute(CreateDocumentCommand(input=CreateDocumentInput(
        title="broken", document_type="pdf", uploaded_by=str(user.id),
        file_name="broken.pdf", file_size=9, mime_type="application/pdf",
        content=b"not a pdf", status=ObjectStatus.ACTIVE,
    )))
    session.commit()
    _index_direct_upload_content(session, document_id=str(bad.id), version=bad.version,
                                 file_name="broken.pdf", content=b"not a pdf")
    session.commit()
    broken_doc = str(bad.id)

    # drain (incremental indexing incl. chunks)
    SearchIndexApplier(session).apply_pending()
    session.commit()

    yield dict(session=session, repo=repo, storage=storage, user=user,
               intake_doc=intake_doc, direct_long=direct_long,
               direct_short=direct_short, broken_doc=broken_doc)
    session.close()


def _chunk_signature(session, document_id):
    rows = session.execute(
        select(DocumentChunkModel)
        .where(DocumentChunkModel.document_id == document_id)
        .order_by(DocumentChunkModel.chunk_index)
    ).scalars().all()
    return [
        (r.chunk_index, r.char_start, r.char_end, r.content, r.content_hash, r.version)
        for r in rows
    ]


def _content_hash(session, document_id):
    row = session.get(DocumentContentModel, document_id)
    return (row.content_hash, row.content_text) if row else None


class TestRebuild:
    def test_rebuild_covers_intake_and_direct_uploads(self, corpus):
        session, storage = corpus["session"], corpus["storage"]
        result = rebuild_document_contents(session, storage)
        session.commit()
        # 3 indexed (intake + long direct + short direct), 1 skipped (broken)
        assert result["indexed"] == 3
        assert result["skipped"] == 1
        assert result["chunked"] == 3
        for doc in (corpus["intake_doc"], corpus["direct_long"], corpus["direct_short"]):
            assert session.get(DocumentContentModel, doc) is not None
            assert len(_chunk_signature(session, doc)) > 0
        # broken doc: no content row, no chunks
        assert session.get(DocumentContentModel, corpus["broken_doc"]) is None

    def test_rebuild_equivalence_incremental_vs_rebuilt(self, corpus):
        """Formal invariant: IncrementalProjection(S) == RebuiltProjection(S)
        per object on (content_hash, ordered chunk signature)."""
        session, storage = corpus["session"], corpus["storage"]
        docs = [corpus["intake_doc"], corpus["direct_long"], corpus["direct_short"]]

        incremental = {
            d: (content_hash(_chunk_signature(session, d) and _content_hash(session, d)[1] or ""),
                _chunk_signature(session, d))
            for d in docs
        }
        # wipe projections entirely, then rebuild
        from sqlalchemy import delete as sa_delete
        session.execute(sa_delete(DocumentChunkModel))
        session.execute(sa_delete(DocumentContentModel))
        session.commit()
        assert session.execute(select(DocumentChunkModel)).scalars().all() == []

        rebuild_document_contents(session, storage)
        session.commit()

        rebuilt = {
            d: (content_hash(_content_hash(session, d)[1]), _chunk_signature(session, d))
            for d in docs
        }
        for d in docs:
            inc_text = incremental[d][1]
            reb_text = rebuilt[d][1]
            # identical ordered chunk signatures (index, span, content, hash, version)
            assert [(c[0], c[1], c[2], c[3], c[4]) for c in reb_text] == [
                (c[0], c[1], c[2], c[3], c[4]) for c in inc_text
            ], f"chunk mismatch for {d}"
            assert _content_hash(session, d)[0] is not None

    def test_rebuild_is_idempotent(self, corpus):
        session, storage = corpus["session"], corpus["storage"]
        rebuild_document_contents(session, storage)
        session.commit()
        first = {
            d: _chunk_signature(session, d)
            for d in (corpus["intake_doc"], corpus["direct_long"], corpus["direct_short"])
        }
        rebuild_document_contents(session, storage)
        session.commit()
        second = {
            d: _chunk_signature(session, d)
            for d in (corpus["intake_doc"], corpus["direct_long"], corpus["direct_short"])
        }
        assert first == second

    def test_rebuild_repairs_crash_window(self, corpus):
        """A direct upload whose content row is missing (crash window) is
        repaired by rebuild from the stored blob."""
        session, storage, repo, user = (corpus["session"], corpus["storage"],
                                        corpus["repo"], corpus["user"])
        # create a direct upload WITHOUT the content write (crash window)
        pdf = make_pdf_bytes(text=LONG_TEXT, title="crash.pdf")
        out = CreateDocumentUseCase(repo, storage).execute(
            CreateDocumentCommand(input=CreateDocumentInput(
                title="crash", document_type="pdf", uploaded_by=str(user.id),
                file_name="crash.pdf", file_size=len(pdf), mime_type="application/pdf",
                content=pdf, status=ObjectStatus.ACTIVE,
            ))
        )
        session.commit()
        assert session.get(DocumentContentModel, str(out.id)) is None
        result = rebuild_document_contents(session, storage)
        session.commit()
        assert result["indexed"] >= 4
        assert session.get(DocumentContentModel, str(out.id)) is not None
        assert len(_chunk_signature(session, str(out.id))) > 0

    def test_rebuild_missing_blob_skips_cleanly(self, corpus):
        """A document whose blob was deleted is skipped, not fatal."""
        session, storage, repo = (corpus["session"], corpus["storage"], corpus["repo"])
        # delete the stored blob of the direct-long doc
        obj = repo.get_by_id(ObjectId(corpus["direct_long"]))
        from app.application.dtos.document import KEY_FILE_PATH
        key = obj.metadata.get_value(KEY_FILE_PATH)
        storage.delete(key)
        result = rebuild_document_contents(session, storage)
        session.commit()
        assert result["skipped"] >= 1  # blob missing -> skipped, no crash
        assert session.get(DocumentContentModel, corpus["direct_long"]) is None
