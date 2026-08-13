"""P1 integration tests: the chunk stage of the AI runtime path.

Verifies that grounded QA actually USES document_chunks as evidence:

- a long document's evidence is the BOUNDED chunk selection (with span
  provenance in the source header), never the whole document text;
- the total evidence per item stays within the existing cap;
- the claim verifier still passes for the exact verbatim answer (CBLU
  regression through the chunk path);
- the FTS projection is queried at retrieval time (bounded, ranked).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.assistant.citations import CitationBuilder
from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.dtos.ai import GenerationResult, TokenUsage
from app.application.dtos.document import CreateDocumentInput
from app.application.commands.create_document import CreateDocumentCommand
from app.application.use_cases.ai.grounded_qa import GroundedQAUseCase
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.api.routes.documents import _index_direct_upload_content
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.document_content_model import DocumentContentModel  # noqa
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel  # noqa
from app.infrastructure.db.models.search_document_model import SearchDocumentModel  # noqa
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa
from app.infrastructure.db.models.object_relationship_model import ObjectRelationshipModel  # noqa
from app.infrastructure.db.models.outbox_model import OutboxEventModel  # noqa
from app.infrastructure.persistence.document_chunk_store import SQLDocumentChunkStore
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.fts import ensure_fts_schema
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.storage.local.local_storage import LocalFileStorage
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.document_annotation_service import DocumentAnnotationService
from app.application.ports.annotation_store import AnnotationStore
from app.tests.unit.extraction_fixtures import make_pdf_bytes

CONF = "In Honor International Conference of Srinivasa Ramanujan's Birthday"
QUERY = (
    'According to the source text of "Cblu Jan, 2024.pdf", what is the full name '
    "of the conference? Do not use or expand the acronym CBLU. Do not infer from "
    "the filename. Give only the conference name explicitly supported by the document."
)
LONG_TEXT = (
    "CERTIFICATE OF PARTICIPATION\n"
    f"This is to certify that Dr Anil Kumar has participated in the {CONF} "
    "organized by Chaudhary Bansi Lal University (CBLU), Bhiwani held on 19 and "
    "20 January 2024 at the university auditorium. "
    + "The conference featured keynote sessions on digital pedagogy, research "
    "ethics and emerging trends in higher education. "
    * 30
    + "This certificate is issued for academic record purposes and may be "
    "verified through the university office.\n"
)


class _AnnStore(AnnotationStore):
    def add(self, a): return a
    def by_document(self, d): return []
    def get(self, i): return None
    def update(self, a): return a
    def delete(self, i): return True


class _Gateway:
    provider_id = "p1-test"
    def __init__(self, answer):
        self._answer = answer
        self.last_prompt = None
    def generate(self, prompt):
        self.last_prompt = prompt
        return GenerationResult(text=self._answer, model="m",
                                usage=TokenUsage(input_tokens=5, output_tokens=7, estimated=True),
                                latency_ms=5)
    def stream(self, prompt):
        yield from []


class _Core:
    def __init__(self, gw): self._gw = gw; self.config = None
    def gateway(self): return self._gw


@pytest.fixture()
def harness(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    ensure_fts_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repo = SQLAlchemyObjectRepository(session)
    storage = LocalFileStorage(str(tmp_path))
    user = UniversalObject.create(
        ObjectType.USER, "anil", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:anil-0001"),
    )
    repo.save(user, outbox_events=[])
    session.commit()

    pdf = make_pdf_bytes(text=LONG_TEXT, title="Cblu Jan, 2024.pdf")
    out = CreateDocumentUseCase(repo, storage).execute(
        CreateDocumentCommand(input=CreateDocumentInput(
            title="Cblu Jan, 2024.pdf", document_type="pdf", uploaded_by=str(user.id),
            file_name="Cblu Jan, 2024.pdf", file_size=len(pdf), mime_type="application/pdf",
            content=pdf, status=ObjectStatus.ACTIVE,
        ))
    )
    _index_direct_upload_content(session, document_id=str(out.id), version=out.version,
                                 file_name="Cblu Jan, 2024.pdf", content=pdf)
    session.commit()
    applier = SearchIndexApplier(session)
    applier.apply_pending()
    session.commit()

    yield dict(session=session, repo=repo, storage=storage, user=user,
               doc_id=str(out.id), applier=applier)
    session.close()


def _qa(harness, gateway):
    session, repo, storage, user = (harness["session"], harness["repo"],
                                    harness["storage"], harness["user"])
    search_uc = SearchObjectsUseCase(
        search_repository=SQLAlchemySearchRepository(session), object_repository=repo,
        permission_evaluator=ObjectPermissionEvaluator(),
    )
    retrieval = AssistantRetrievalService(
        search_uc, GraphRuntimeService(repo, ObjectPermissionEvaluator()), repository=repo,
    )
    ann = DocumentAnnotationService(repo, _AnnStore(), content_store=SQLDocumentContentStore(session))
    return GroundedQAUseCase(
        repository=repo, retrieval=retrieval, ai_core=_Core(gateway),
        annotation_service=ann, storage=storage,
        chunk_store=SQLDocumentChunkStore(session),
    )


class TestChunkEvidencePath:
    def test_chunks_created_for_long_doc(self, harness):
        assert harness["applier"].stats["chunk_created"] >= 1
        rows = SQLDocumentChunkStore(harness["session"]).by_document(harness["doc_id"])
        assert len(rows) > 1  # long document -> multiple chunks

    def test_fts_used_at_retrieval_time(self, harness):
        repo = SQLAlchemySearchRepository(harness["session"])
        hits = repo.search(text="ramanujan birthday", limit=8)
        assert harness["doc_id"] in {h.object_id for h in hits}
        assert repo.search(text="zebraquirkzz", limit=8) == []

    def test_evidence_is_bounded_chunks_not_whole_document(self, harness):
        gw = _Gateway(CONF)
        qa = _qa(harness, gw)
        out = qa.execute(QUERY, harness["user"])
        user_msg = gw.last_prompt.user
        src = user_msg[user_msg.find("SOURCE CONTENT"):]
        # provenance header present
        assert "chunks " in src and "chars " in src
        # bounded: evidence < whole document (LONG_TEXT is ~7 KB)
        block = src[src.find("<<<SOURCE TEXT>>>") + len("<<<SOURCE TEXT>>>"):src.find("<<<END>>>")]
        assert len(block) < len(LONG_TEXT)
        assert len(block) <= 2000
        # the exact conference name is inside the chunk evidence
        assert CONF in block

    def test_cblu_regression_through_chunk_path(self, harness):
        # The branch carries the evidence GATE (doc-ref resolution); the
        # claim-support verifier is a separate prior deliverable that is
        # NOT present in the pushed branch (see P1 report). This test pins
        # the chunk-path behavior that exists: the referenced document is
        # resolved, its chunk evidence reaches the prompt, the answer is
        # generated (no gate refusal) and the citation points at the target.
        gw = _Gateway(CONF)
        qa = _qa(harness, gw)
        out = qa.execute(QUERY, harness["user"])
        assert "could not verify" not in out.answer
        assert out.answer == CONF
        assert any(c["object_id"] == harness["doc_id"] for c in out.citations)


    def test_unsupported_expansion_refused_through_chunk_path(self, harness):
        """The unsupported claim 'CBLU (Chaudhary Bansi Lal University)' must
        be REFUSED through the chunk path: the chunk evidence contains the
        conference name (no expansion), so the answer expanding the acronym
        fails the deterministic verbatim/acronym check."""
        gw = _Gateway("CBLU (Chaudhary Bansi Lal University)")
        qa = _qa(harness, gw)
        out = qa.execute(QUERY, harness["user"])
        assert out.claim_supported is False
        assert out.claim_mode == "extraction"
        assert "could not be verified" in out.answer
        assert out.citations == ()

    def test_supported_claim_has_claim_fields(self, harness):
        gw = _Gateway(CONF)
        qa = _qa(harness, gw)
        out = qa.execute(QUERY, harness["user"])
        assert out.claim_supported is True
        assert out.claim_mode == "extraction"
        assert any(c["object_id"] == harness["doc_id"] for c in out.citations)
    def test_evidence_gate_refuses_unresolved_reference(self, harness):
        gw = _Gateway("anything")
        qa = _qa(harness, gw)
        out = qa.execute(
            'According to the source text of "missing-file.pdf", what is the name?',
            harness["user"],
        )
        assert "could not verify" in out.answer
