"""P1 maintenance regression tests: citations represent SUPPORTING EVIDENCE.

Graph-only related objects (discovered via the graph leg's BELONGS_TO
traversal) must NOT be presented as citations/sources, and their structured
metadata must NOT leak into the prompt. Search-hit objects — including
structured objects such as events — keep their citation + metadata behavior.

Covered scenarios (mandated):
1. certificate document is a search hit; the "Ku conference" EVENT is
   reachable only via the BELONGS_TO graph edge:
   - certificate remains citation [1]
   - graph-only event is NOT a citation
   - graph-only event metadata is NOT rendered into retrieved evidence
   - graph-only event does NOT appear in SOURCE CONTENT
2. a genuine search-hit event question:
   - event remains citable
   - its metadata remains available
   - structured-object answer still works
3. a graph-only DOCUMENT (with text) is not numbered / not in SOURCE CONTENT
4. CBLU supported / unsupported-claim refusal unchanged
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
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
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
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.storage.local.local_storage import LocalFileStorage
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.document_annotation_service import DocumentAnnotationService
from app.application.ports.annotation_store import AnnotationStore
from app.tests.unit.extraction_fixtures import make_pdf_bytes

CERT_TEXT = (
    "CERTIFICATE\n"
    "This is to certify that Mr. Vipin Gupta has presented a paper at the "
    "XXVII Annual Conference (CONIAPS XXVII) held during October 26-28, 2021 "
    "organized by the Department of Mathematics, Kurukshetra University, "
    "Kurukshetra, India.\n"
    "Title of the paper: Wave propagation in homogenous solids with porosity "
    "under liquid half-space.\n"
    "This certificate is issued for academic record purposes.\n"
)
PAPER_TITLE = (
    "Wave propagation in homogenous solids with porosity under liquid half-space"
)
CONF = "In Honor International Conference of Srinivasa Ramanujan's Birthday"

Q_TITLE = "What is the exact title of the paper mentioned in the certificate issued to Vipin Gupta?"
Q_ORGANIZER = "Who organized the conference mentioned in the certificate issued to Vipin Gupta?"
Q_EVENT = "When was the Ku conference held?"


def _h(k, v):
    return MetadataEntry(k, v, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)


class _S(AnnotationStore):
    def add(self, a): return a
    def by_document(self, d): return []
    def get(self, i): return None
    def update(self, a): return a
    def delete(self, i): return True


class _Gateway:
    provider_id = "t"
    def __init__(self, answer):
        self._answer = answer
        self.last_prompt = None
    def generate(self, prompt):
        self.last_prompt = prompt
        return GenerationResult(text=self._answer, model="m",
                                usage=TokenUsage(estimated=True), latency_ms=1)
    def stream(self, prompt):
        yield from []


class _Core:
    def __init__(self, g):
        self._g = g
        self.config = None
    def gateway(self):
        return self._g


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
    creator = CreateDocumentUseCase(repo, storage)

    # EVENT "Ku conference" (structured object with organizer/location/date)
    ev = UniversalObject.create(
        ObjectType.EVENT, "Ku conference", created_by=str(user.id),
        status=ObjectStatus.ACTIVE,
        metadata=Metadata(entries=(
            _h("event.date_start", "2021-10-26"),
            _h("event.date_end", "2021-10-28"),
            _h("event.organizer", "Department of Mathematics, Kurukshetra University"),
            _h("event.location", "Kurukshetra University, Kurukshetra, India"),
            _h("event.acronym", "CONIAPS XXVII"),
        )),
    )
    repo.save(ev, outbox_events=[])
    session.commit()
    ev_id = str(ev.id)

    # certificate document LINKED to the event (BELONGS_TO via object_id)
    pdf = make_pdf_bytes(text=CERT_TEXT, title="22 dec.pdf")
    out = creator.execute(CreateDocumentCommand(input=CreateDocumentInput(
        title="22 dec.pdf", document_type="pdf", uploaded_by=str(user.id),
        file_name="22 dec.pdf", file_size=len(pdf), mime_type="application/pdf",
        content=pdf, status=ObjectStatus.ACTIVE, object_id=ev_id,
    )))
    session.commit()
    _index_direct_upload_content(session, document_id=str(out.id), version=out.version,
                                 file_name="22 dec.pdf", content=pdf)
    session.commit()
    doc_id = str(out.id)

    # a SECOND document, graph-only for the certificate questions, WITH text
    # (a neighbor whose text must not become numbered evidence either)
    pdf2 = make_pdf_bytes(text="Attached supplementary notes about wave propagation.\n", title="notes.pdf")
    out2 = creator.execute(CreateDocumentCommand(input=CreateDocumentInput(
        title="notes.pdf", document_type="pdf", uploaded_by=str(user.id),
        file_name="notes.pdf", file_size=len(pdf2), mime_type="application/pdf",
        content=pdf2, status=ObjectStatus.ACTIVE, object_id=ev_id,
    )))
    session.commit()
    _index_direct_upload_content(session, document_id=str(out2.id), version=out2.version,
                                 file_name="notes.pdf", content=pdf2)
    session.commit()
    notes_id = str(out2.id)

    SearchIndexApplier(session).apply_pending()
    session.commit()

    yield dict(session=session, repo=repo, storage=storage, user=user,
               doc_id=doc_id, ev_id=ev_id, notes_id=notes_id)
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
    ann = DocumentAnnotationService(repo, _S(), content_store=SQLDocumentContentStore(session))
    return GroundedQAUseCase(
        repository=repo, retrieval=retrieval, ai_core=_Core(gateway),
        annotation_service=ann, storage=storage,
        chunk_store=SQLDocumentChunkStore(session),
    )


def _retrieve(harness, q):
    """Direct retrieval trace for assertions."""
    session, repo, user = harness["session"], harness["repo"], harness["user"]
    search_uc = SearchObjectsUseCase(
        search_repository=SQLAlchemySearchRepository(session), object_repository=repo,
        permission_evaluator=ObjectPermissionEvaluator(),
    )
    retrieval = AssistantRetrievalService(
        search_uc, GraphRuntimeService(repo, ObjectPermissionEvaluator()), repository=repo,
    )
    return retrieval.retrieve(q, user)


class TestGraphOnlyNotCitable:
    def test_graph_only_event_not_cited_and_metadata_suppressed(self, harness):
        """Certificate is a search hit; the event is reachable ONLY via the
        BELONGS_TO graph edge."""
        gw = _Gateway(PAPER_TITLE)
        qa = _qa(harness, gw)
        out = qa.execute(Q_TITLE, harness["user"])
        prompt = gw.last_prompt.user

        # citations: ONLY the certificate
        ids = [c["object_id"] for c in out.citations]
        assert harness["doc_id"] in ids
        assert harness["ev_id"] not in ids
        assert len(out.citations) == 1

        # the graph-only event's metadata is NOT rendered into the prompt
        assert "Ku conference" in prompt  # title line may remain (context)
        assert "event.organizer" not in prompt
        assert "event.location" not in prompt
        assert "event.acronym" not in prompt

        # the event does not appear in SOURCE CONTENT
        sc = prompt[prompt.find("SOURCE CONTENT"):]
        assert "Ku conference" not in sc

    def test_graph_only_event_not_cited_organizer_question(self, harness):
        gw = _Gateway("Department of Mathematics, Kurukshetra University, India.")
        qa = _qa(harness, gw)
        out = qa.execute(Q_ORGANIZER, harness["user"])
        ids = [c["object_id"] for c in out.citations]
        assert harness["doc_id"] in ids
        assert harness["ev_id"] not in ids
        assert len(out.citations) == 1
        prompt = gw.last_prompt.user
        assert "event.organizer" not in prompt  # no label leak vector

    def test_graph_only_document_with_text_not_numbered(self, harness):
        """A document discovered ONLY via the graph leg (text present) must
        not be numbered nor rendered in SOURCE CONTENT."""
        gw = _Gateway(PAPER_TITLE)
        qa = _qa(harness, gw)
        out = qa.execute(Q_TITLE, harness["user"])
        prompt = gw.last_prompt.user
        ids = [c["object_id"] for c in out.citations]
        assert harness["notes_id"] not in ids
        sc = prompt[prompt.find("SOURCE CONTENT"):]
        assert "notes.pdf" not in sc


class TestSearchHitEventStillCitable:
    def test_event_search_hit_cited_with_metadata(self, harness):
        """A genuine search-hit question about the event keeps citation +
        metadata — structured-object questions still work."""
        gw = _Gateway("26-28 October 2021")
        qa = _qa(harness, gw)
        out = qa.execute(Q_EVENT, harness["user"])
        prompt = gw.last_prompt.user
        ids = [c["object_id"] for c in out.citations]
        assert harness["ev_id"] in ids
        # event metadata still rendered for a citable search hit
        assert "event.date_start" in prompt
        # certificate may or may not also match; the event MUST be cited
        assert any(c["title"] == "Ku conference" for c in out.citations)

    def test_search_hit_event_metadata_available(self, harness):
        session, repo, user = harness["session"], harness["repo"], harness["user"]
        search_uc = SearchObjectsUseCase(
            search_repository=SQLAlchemySearchRepository(session), object_repository=repo,
            permission_evaluator=ObjectPermissionEvaluator(),
        )
        res = search_uc.execute(user=user, text="ku conference", limit=8)
        assert harness["ev_id"] in {h.object_id for h in res}


class TestCBLURegressionThroughFilter:
    def test_supported_claim_still_passes(self, harness):
        # CBLU-style doc-ref question on a doc with verbatim claim: the
        # referenced doc is a search hit (doc-ref resolution) -> citable,
        # and the supported verbatim answer keeps the citation.
        gw = _Gateway(PAPER_TITLE)
        qa = _qa(harness, gw)
        out = qa.execute(
            'According to the source text of "22 dec.pdf", what is the exact title of the paper?',
            harness["user"],
        )
        assert out.claim_supported is True
        assert any(c["object_id"] == harness["doc_id"] for c in out.citations)

    def test_unsupported_claim_refused_no_citation(self, harness):
        gw = _Gateway("CBLU (Chaudhary Bansi Lal University)")
        qa = _qa(harness, gw)
        out = qa.execute(
            'According to the source text of "Cblu Jan, 2024.pdf", what is the '
            "full name of the conference? Do not use or expand the acronym CBLU.",
            harness["user"],
        )
        # unresolved reference -> evidence gate refusal, no citations
        assert out.citations == ()
        assert "could not verify" in out.answer
