"""P0 foundation tests: document-reference resolution, candidate-window
integrity, workflow-object exclusion, and the deterministic evidence gate.

Architectural contract (not per-bug tests):

1. A query naming a document ("According to the source text of "Cblu Jan,
   2024.pdf" ...") must resolve that document by EXACT filename/title before
   any fuzzy retrieval, and the resolution must survive into the evidence.
2. Internal/workflow objects (AI_CONVERSATION, USER, INTAKE_ITEM,
   INTAKE_SESSION) must be excluded IN THE SQL WHERE clause — they can never
   consume the candidate window and starve real evidence.
3. When the referenced document is missing from the evidence (or its source
   text is unavailable), grounded QA must refuse deterministically instead of
   answering from other documents or conversation history.
4. Global search (no exclusion) is unchanged.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.application.dtos.assistant import AssistantRetrievalResult, RetrievedItem
from app.application.services.assistant_retrieval import (
    AssistantRetrievalService,
    RetrievalPlan,
    _document_reference,
    retrieval_plan,
)
from app.application.use_cases.ai.grounded_qa import GroundedQAUseCase
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.application.commands.create_document import CreateDocumentCommand
from app.application.dtos.document import CreateDocumentInput
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.api.routes.documents import _index_direct_upload_content
from app.application.services.graph_runtime import GraphRuntimeService
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import MetadataLayer, ObjectStatus, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.document_content_model import DocumentContentModel  # noqa
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa
from app.infrastructure.db.models.object_relationship_model import ObjectRelationshipModel  # noqa
from app.infrastructure.db.models.outbox_model import OutboxEventModel  # noqa
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.storage.local.local_storage import LocalFileStorage
from app.tests.unit.extraction_fixtures import make_pdf_bytes

Q2 = (
    'According to the source text of "Cblu Jan, 2024.pdf", what is the full name '
    "of the conference? Do not use or expand the acronym CBLU. Do not infer from "
    "the filename. Give only the conference name explicitly supported by the document."
)
BODY = (
    "CERTIFICATE OF PARTICIPATION\nThis is to certify that Dr Anil Kumar participated "
    "in the In Honor International Conference of Srinivasa Ramanujan's Birthday "
    "organized by Chaudhary Bansi Lal University (CBLU), Bhiwani held on 19 and 20 "
    "January 2024.\n"
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

    creator = CreateDocumentUseCase(repo, storage)

    def upload(file_name, title):
        pdf = make_pdf_bytes(text=BODY, title=file_name)
        out = creator.execute(CreateDocumentCommand(input=CreateDocumentInput(
            title=title, document_type="pdf", uploaded_by=str(user.id),
            file_name=file_name, file_size=len(pdf), mime_type="application/pdf",
            content=pdf, status=ObjectStatus.ACTIVE)))
        session.commit()
        _index_direct_upload_content(session, document_id=str(out.id), version=out.version,
                                     file_name=file_name, content=pdf)
        session.commit()
        return str(out.id)

    # The referenced document: USER-ENTERED TITLE differs from the filename
    # (the realistic case that broke the browser attribution test).
    target = upload("Cblu Jan, 2024.pdf", "Certificate of Participation")
    upload("CBLU Jan 2025.pdf", "CBLU Jan 2025 Certificate")

    # Noise + many conversations + an intake session ("Folder import — Personal")
    for i in range(6):
        upload(f"CBLU Workshop {i}.pdf", f"CBLU Workshop {i}")
    convs = []
    for i in range(10):
        conv = UniversalObject.create(
            ObjectType.AI_CONVERSATION, f"CBLU chat {i}", created_by=str(user.id),
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(entries=(
                _entry("msg.1", '{"role": "user", "content": "What about the CBLU conference in January 2024?"}'),
                _entry("msg.2", '{"role": "assistant", "content": "CBLU (Chaudhary Bansi Lal University) held a conference."}'),
            )),
        )
        repo.save(conv, outbox_events=[])
        convs.append(str(conv.id))
    intake_session = UniversalObject.create(
        ObjectType.INTAKE_SESSION, "Folder import — Personal", created_by="intake",
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=(_entry("intake.status", "completed"),)),
    )
    repo.save(intake_session, outbox_events=[])
    session.commit()

    SearchIndexApplier(session).apply_pending()
    session.commit()
    return dict(session=session, repo=repo, storage=storage, user=user,
                target=target, convs=convs, intake_session=str(intake_session.id))


def _retrieval(harness):
    session, repo = harness["session"], harness["repo"]
    search_repo = SQLAlchemySearchRepository(session)
    search_uc = SearchObjectsUseCase(
        search_repository=search_repo, object_repository=repo,
        permission_evaluator=ObjectPermissionEvaluator(),
    )
    return AssistantRetrievalService(
        search_uc, GraphRuntimeService(repo, ObjectPermissionEvaluator()), repository=repo
    )


# ---------------------------------------------------------------- plan level
class TestDocumentReferencePlan:
    def test_quoted_filename_is_document_reference(self):
        plan = retrieval_plan(Q2)
        assert plan.document_ref == "Cblu Jan, 2024.pdf"
        assert plan.terms == ("Cblu Jan, 2024.pdf",)

    def test_bare_filename_is_document_reference(self):
        plan = retrieval_plan("What does Cblu Jan, 2024.pdf say about the conference?")
        assert plan.document_ref == "Cblu Jan, 2024.pdf"

    def test_entity_query_has_no_document_reference(self):
        plan = retrieval_plan("When did I attend the CBLU conference?")
        assert plan.document_ref is None
        assert plan.terms == ("cblu",)

    def test_fact_query_has_no_document_reference(self):
        plan = retrieval_plan("Which conference did I attend in January 2024?")
        assert plan.document_ref is None
        assert plan.object_type == "event"

    def test_plain_prose_never_treated_as_filename(self):
        assert _document_reference("what is the CBLU document about") is None
        assert _document_reference("tell me about the conference PDF") is None


# --------------------------------------------------------- resolution level
class TestDocumentReferenceResolution:
    def test_exact_filename_resolution_finds_target(self, harness):
        svc = _retrieval(harness)
        result = svc.retrieve(Q2, harness["user"])
        assert result.document_reference == "Cblu Jan, 2024.pdf"
        assert result.document_reference_resolved is True
        assert result.resolved_document_id == harness["target"]
        assert any(it.object_id == harness["target"] for it in result.items)

    def test_window_starvation_prevented_with_ten_conversations(self, harness):
        # 10 conversations containing 'cblu' previously filled the limit-8
        # window; now they are excluded in SQL and the target survives.
        session = harness["session"]
        repo_search = SQLAlchemySearchRepository(session)
        rows = repo_search.search(text="cblu", exclude_types={"ai_conversation", "user",
                                                              "intake_item", "intake_session"},
                                  limit=8)
        assert all(r.object_type != "ai_conversation" for r in rows)
        assert harness["target"] in {r.object_id for r in rows}

    def test_retrieval_excludes_workflow_and_internal_types(self, harness):
        svc = _retrieval(harness)
        result = svc.retrieve("CBLU conference", harness["user"])
        types = {it.object_type for it in result.items}
        assert "ai_conversation" not in types
        assert "intake_session" not in types
        assert "intake_item" not in types

    def test_global_search_unchanged_without_exclusions(self, harness):
        # GET /search passes no exclude_types → conversations remain
        # searchable there (documented: exclusion is AI-evidence-only).
        session = harness["session"]
        rows = SQLAlchemySearchRepository(session).search(text="cblu", limit=50)
        assert any(r.object_type == "ai_conversation" for r in rows)


# ------------------------------------------------------------ evidence gate
class _StubRetrieval:
    def __init__(self, result):
        self._result = result

    def retrieve(self, question, user):
        return self._result


class _BoomGateway:
    """Raises if the gateway is ever called — the gate must prevent it."""

    def gateway(self):
        raise AssertionError("gateway must not be called when the evidence gate refuses")


class _StubAnnotation:
    def __init__(self, text):
        self._text = text

    def extracted_text(self, document_id, storage):
        return {"text": self._text} if self._text else None


class TestEvidenceGate:
    def _qa(self, retrieval_result, annotation=None):
        return GroundedQAUseCase(
            repository=object(),
            retrieval=_StubRetrieval(retrieval_result),
            ai_core=_BoomGateway(),
            annotation_service=annotation,
            storage=object(),
        )

    def _item(self, object_id):
        return RetrievedItem(
            object_id=object_id, object_type="document", title="Cblu Jan, 2024.pdf",
            version=1, sources=("search",), score=1.0, metadata_text="file_name: Cblu Jan, 2024.pdf",
        )

    def test_refuses_when_referenced_document_not_retrieved(self):
        result = AssistantRetrievalResult(
            items=tuple([self._item("obj:document:other")]),
            search_count=1, graph_count=0,
            document_reference="Cblu Jan, 2024.pdf",
            document_reference_resolved=False,
        )
        qa = self._qa(result)
        out = qa.execute(Q2, object())
        assert "could not verify the answer from the specified document" in out.answer
        assert out.available is True
        assert out.citations == ()

    def test_refuses_when_source_text_unavailable(self):
        result = AssistantRetrievalResult(
            items=tuple([self._item("obj:document:target")]),
            search_count=1, graph_count=0,
            document_reference="Cblu Jan, 2024.pdf",
            document_reference_resolved=True,
            resolved_document_id="obj:document:target",
        )
        qa = self._qa(result, annotation=_StubAnnotation(None))  # no source text
        out = qa.execute(Q2, object())
        assert "could not verify the answer from the specified document" in out.answer

    def test_stream_refuses_with_completion_only(self):
        result = AssistantRetrievalResult(
            items=tuple([self._item("obj:document:other")]),
            search_count=1, graph_count=0,
            document_reference="Cblu Jan, 2024.pdf",
            document_reference_resolved=False,
        )
        qa = self._qa(result)
        events = list(qa.stream(Q2, object()))
        assert len(events) == 1
        assert events[0]["type"] == "complete"
        assert "could not verify" in events[0]["result"].answer

    def test_gate_passes_when_referenced_document_has_source_text(self):
        result = AssistantRetrievalResult(
            items=tuple([self._item("obj:document:target")]),
            search_count=1, graph_count=0,
            document_reference="Cblu Jan, 2024.pdf",
            document_reference_resolved=True,
            resolved_document_id="obj:document:target",
        )
        qa = self._qa(result, annotation=_StubAnnotation(BODY))
        out = qa.execute(Q2, object())
        # Not a refusal: the gateway path is taken (boom gateway → honest
        # fallback because no provider exists in the test, which is NOT the
        # evidence-gate refusal).
        assert "could not verify the answer from the specified document" not in out.answer

    def test_gate_ignored_when_no_document_reference(self):
        result = AssistantRetrievalResult(
            items=tuple([self._item("obj:document:x")]),
            search_count=1, graph_count=0,
        )
        qa = self._qa(result)
        out = qa.execute("When did I attend the CBLU conference?", object())
        assert "could not verify the answer from the specified document" not in out.answer
