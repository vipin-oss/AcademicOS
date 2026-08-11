"""Unit tests: direct-upload document content indexing (Fix A).

A directly-uploaded PDF/DOCX (via ``POST /documents``) gets its BODY text
indexed into the existing ``document_contents`` projection right after
``CreateDocumentUseCase`` succeeds:

- ``documents.py:_index_direct_upload_content`` parses the uploaded bytes
  with the existing M2 parser registry and writes the projection through
  the same ``SQLDocumentContentStore`` seam the intake commit uses;
- ``DocumentAnnotationService.extracted_text`` falls back to that row when
  the document has no linked intake item;
- the existing SQL content-search leg surfaces body-only terms.

Graceful degradation: unsupported formats, corrupt files and empty text
skip the content row — the upload itself always succeeds.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.routes.documents import _index_direct_upload_content
from app.application.commands.create_document import CreateDocumentCommand
from app.application.dtos.document import CreateDocumentInput
from app.application.services.document_annotation_service import (
    DocumentAnnotationService,
)
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.document_content_model import DocumentContentModel
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.storage.local.local_storage import LocalFileStorage

from app.tests.unit.extraction_fixtures import make_docx_bytes, make_pdf_bytes

BODY = (
    "This report describes the quantum entanglement experiments conducted "
    "in the superconducting laboratory during 2025. The results were "
    "presented at the annual symposium on 17 March 2026."
)


@pytest.fixture()
def harness(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    repo = SQLAlchemyObjectRepository(session)
    storage = LocalFileStorage(str(tmp_path))

    user = UniversalObject.create(
        ObjectType.USER, "uploader", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:du-0001"),
    )
    repo.save(user, outbox_events=[])
    session.commit()
    yield session, repo, storage, user
    session.close()


def _upload(session, repo, storage, user, *, file_name: str, content: bytes,
            title: str = "Direct Upload"):
    """The exact route sequence: use case first, content indexing second."""
    out = CreateDocumentUseCase(repo, storage).execute(
        CreateDocumentCommand(
            input=CreateDocumentInput(
                title=title,
                document_type="pdf" if file_name.endswith(".pdf") else "docx",
                uploaded_by=str(user.id),
                file_name=file_name,
                file_size=len(content),
                mime_type="application/octet-stream",
                content=content,
                status=ObjectStatus.ACTIVE,
                object_id=None,
            )
        )
    )
    _index_direct_upload_content(
        session,
        document_id=str(out.id),
        version=out.version,
        file_name=file_name,
        content=content,
    )
    session.commit()
    return out


def _content_row(session, object_id):
    return session.execute(
        select(DocumentContentModel).where(DocumentContentModel.object_id == object_id)
    ).scalar_one_or_none()


def test_direct_pdf_upload_creates_content_projection_with_body_text(harness):
    session, repo, storage, user = harness
    pdf = make_pdf_bytes(text=BODY, title="report.pdf")
    out = _upload(session, repo, storage, user, file_name="report.pdf", content=pdf)

    row = _content_row(session, str(out.id))
    assert row is not None, "no document_contents row for the direct upload"
    assert "entanglement" in row.content_text
    assert "17 March 2026" in row.content_text
    # Self-provenance: no intake item exists for a direct upload.
    assert row.source_item_id == str(out.id)


def test_direct_docx_upload_creates_content_projection_with_body_text(harness):
    session, repo, storage, user = harness
    docx = make_docx_bytes(lines=BODY.splitlines(), title="report.docx")
    out = _upload(session, repo, storage, user, file_name="report.docx", content=docx)

    row = _content_row(session, str(out.id))
    assert row is not None, "no document_contents row for the direct DOCX upload"
    assert "entanglement" in row.content_text
    assert row.source_item_id == str(out.id)


def test_body_only_term_searchable_through_existing_sql_content_leg(harness):
    session, repo, storage, user = harness
    pdf = make_pdf_bytes(text=BODY, title="opaque-name.pdf")
    out = _upload(session, repo, storage, user, file_name="opaque-name.pdf", content=pdf)

    # The search-documents projection is drained by the outbox relay exactly
    # as at AI-read time (ai.py:_qa_retrieval); the content row rides the
    # same corpus. The body term exists NOWHERE in title/metadata.
    SearchIndexApplier(session).apply_pending()
    session.commit()
    hits = SQLAlchemySearchRepository(session).search(text="superconducting", limit=10)
    assert str(out.id) in {h.object_id for h in hits}
    hits = SQLAlchemySearchRepository(session).search(text="17 march 2026", limit=10)
    assert str(out.id) in {h.object_id for h in hits}


def test_extracted_text_falls_back_to_direct_upload_content(harness):
    session, repo, storage, user = harness
    pdf = make_pdf_bytes(text=BODY, title="report.pdf")
    out = _upload(session, repo, storage, user, file_name="report.pdf", content=pdf)

    service = DocumentAnnotationService(
        repo, _FakeAnnotationStore(), content_store=SQLDocumentContentStore(session)
    )
    result = service.extracted_text(str(out.id), storage)
    assert result is not None
    assert "entanglement" in result["text"]
    assert result["source"] == "document_content"
    assert result["session_id"] == ""
    assert result["item_id"] == ""


def test_extracted_text_without_content_store_keeps_old_behavior(harness):
    session, repo, storage, user = harness
    pdf = make_pdf_bytes(text=BODY, title="report.pdf")
    out = _upload(session, repo, storage, user, file_name="report.pdf", content=pdf)

    # No content store wired -> the pre-fix behavior: None for direct uploads.
    service = DocumentAnnotationService(repo, _FakeAnnotationStore())
    assert service.extracted_text(str(out.id), storage) is None


def test_unsupported_format_degrades_without_failing_upload(harness):
    session, repo, storage, user = harness
    out = _upload(
        session, repo, storage, user,
        file_name="notes.xyz", content=b"no parser family for xyz",
        title="Notes",
    )
    assert _content_row(session, str(out.id)) is None
    assert out.id is not None, "the upload itself still succeeded"


def test_corrupt_pdf_degrades_without_failing_upload(harness):
    session, repo, storage, user = harness
    out = _upload(
        session, repo, storage, user,
        file_name="broken.pdf", content=b"this is definitely not a pdf",
        title="Broken",
    )
    assert _content_row(session, str(out.id)) is None
    assert out.id is not None, "the upload itself still succeeded"


def test_empty_extracted_text_skips_content_row(harness):
    session, repo, storage, user = harness
    pdf = make_pdf_bytes(text="   \n  ", title="blank.pdf")
    out = _upload(session, repo, storage, user, file_name="blank.pdf", content=pdf)
    assert _content_row(session, str(out.id)) is None


class _FakeAnnotationStore:
    """Minimal AnnotationStore stand-in for the extracted-text tests."""

    def add(self, annotation):
        return annotation

    def by_document(self, document_id):
        return []

    def get(self, annotation_id):
        return None

    def update(self, annotation):
        return annotation

    def delete(self, annotation_id):
        return True
