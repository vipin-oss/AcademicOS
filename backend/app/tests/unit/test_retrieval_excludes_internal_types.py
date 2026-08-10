"""Regression tests: AI retrieval excludes internal object types.

Confirmed root cause: AI_CONVERSATION objects are indexed in
``search_documents`` and were eligible for the AI retrieval search leg
(no object_type restriction), so old conversation titles/content could
surface as AI sources (e.g. a stored "AcademicOS OK" message being cited
and reproduced).

Fix: ``AssistantRetrievalService.retrieve`` drops internal types
(AI_CONVERSATION, USER) from the search leg for GENERAL retrieval
(``object_type=None``). Explicit type requests — the memory-recall path
searches AI_CONVERSATION on purpose — are preserved. Global search
(``SearchObjectsUseCase`` used by ``GET /search``) is untouched: the
exclusion lives in the assistant retrieval service only.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.use_cases.auth.helpers import get_roles
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.search_document_model import SearchDocumentModel
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier


# ---------------------------------------------------------------------------
# Unit level: fake search leg
# ---------------------------------------------------------------------------

class _FakeSearch:
    """Records the query text and returns canned hits per text."""

    def __init__(self, hits_by_text: dict):
        self.hits_by_text = hits_by_text
        self.calls: list[tuple] = []

    def execute(self, *, user, text, object_type=None, limit=8):
        self.calls.append((text, object_type))
        return self.hits_by_text.get(text, [])


class _FakeGraph:
    def traverse(self, *args, **kwargs):
        return {"items": []}


class _User:
    id = "obj:user:test-0001"

    class _Meta:
        def get_value(self, key):
            return None

    metadata = _Meta()


_USER = _User()


class _FakeHit:
    def __init__(self, object_id, object_type, title, version=1, score=0.5,
                 metadata_text=""):
        self.object_id = object_id
        self.object_type = object_type
        self.title = title
        self.version = version
        self.score = score
        self.metadata_text = metadata_text
        self.index_source = "lexical"


def _service(search, graph=None):
    return AssistantRetrievalService(search, graph or _FakeGraph())


def test_conversation_hit_matching_query_never_appears_in_results():
    """An AI_CONVERSATION matching 'hello' must never be in the results."""
    conv = _FakeHit("obj:ai_conversation:1", "ai_conversation", "hello")
    doc = _FakeHit("obj:document:1", "document", "hello report")
    search = _FakeSearch({"hello": [conv, doc]})

    result = _service(search).retrieve("hello", _USER)

    assert [i.object_id for i in result.items] == ["obj:document:1"]
    assert all(i.object_type != "ai_conversation" for i in result.items)


def test_conversation_with_canned_content_never_becomes_evidence():
    """A conversation whose stored content is 'AcademicOS OK' must never be
    an AI source (title must not appear in the retrieved items)."""
    conv = _FakeHit(
        "obj:ai_conversation:9", "ai_conversation", "AcademicOS OK",
        metadata_text="msg.1: Reply with exactly: AcademicOS OK",
    )
    doc = _FakeHit("obj:document:2", "document", "hello report")
    search = _FakeSearch({"hello": [conv, doc]})

    result = _service(search).retrieve("hello", _USER)

    assert all(i.object_id != "obj:ai_conversation:9" for i in result.items)
    assert all("AcademicOS OK" != i.title for i in result.items)


def test_legitimate_academic_object_still_retrieved():
    """A legitimate document matching the same query is still retrieved."""
    doc = _FakeHit("obj:document:3", "document", "hello report")
    search = _FakeSearch({"hello": [doc]})

    result = _service(search).retrieve("hello", _USER)

    assert [i.object_id for i in result.items] == ["obj:document:3"]


def test_user_hits_are_excluded_too():
    user_hit = _FakeHit("obj:user:5", "user", "vipin gupta")
    doc = _FakeHit("obj:document:4", "document", "hello")
    search = _FakeSearch({"hello": [user_hit, doc]})

    result = _service(search).retrieve("hello", _USER)

    assert [i.object_id for i in result.items] == ["obj:document:4"]


def test_singular_fallback_after_conversation_only_hits():
    """If the primary term returns only conversations (filtered to zero),
    the singular fallback still runs and can surface academic objects."""
    conv = _FakeHit("obj:ai_conversation:2", "ai_conversation", "grants")
    grant = _FakeHit("obj:grant:1", "grant", "Grant 001")
    search = _FakeSearch({"grants": [conv], "grant": [grant]})

    result = _service(search).retrieve("What research grants do I have?", _USER)

    assert search.calls[0] == ("grants", None)
    assert search.calls[1] == ("grant", None)  # fallback fired after filtering
    assert [i.object_id for i in result.items] == ["obj:grant:1"]


def test_memory_recall_explicit_conversation_type_is_preserved():
    """Memory recall searches AI_CONVERSATION on purpose — an explicit
    object_type must NOT be filtered."""
    conv = _FakeHit("obj:ai_conversation:3", "ai_conversation", "hello")
    search = _FakeSearch({"hello": [conv]})

    result = _service(search).retrieve(
        "hello", _USER, object_type=ObjectType.AI_CONVERSATION.value
    )

    assert [i.object_id for i in result.items] == ["obj:ai_conversation:3"]


# ---------------------------------------------------------------------------
# Integration level: real SQLite + outbox-fed index + real search use case
# ---------------------------------------------------------------------------

@pytest.fixture()
def world():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    repo = SQLAlchemyObjectRepository(session)
    yield session, repo
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _save_indexed(repo, obj):
    from app.application.services.outbox import to_outbox_row

    events = obj.pop_domain_events()
    repo.save(obj, outbox_events=[to_outbox_row(e) for e in events])


def _user():
    return UniversalObject.create(
        ObjectType.USER, "tester", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:retr-0001"),
    )


def test_indexed_conversation_never_retrieved_but_global_search_still_finds_it(world):
    """End-to-end: an indexed AI_CONVERSATION matching 'hello' (with stored
    'AcademicOS OK' content) is excluded from AssistantRetrievalService,
    while GET /search's own repository still returns it (global search and
    the index are untouched)."""
    session, repo = world

    # conversation with stored messages (the contamination vector)
    conv = UniversalObject.create(
        ObjectType.AI_CONVERSATION, "hello", created_by="u:1",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:ai_conversation:retr-0001"),
    )
    from app.application.use_cases.assistant.helpers import append_message

    append_message(conv, "user", "hello", None)
    append_message(conv, "assistant", "AcademicOS OK", None)
    _save_indexed(repo, conv)

    # legitimate document matching the same query
    doc = UniversalObject.create(
        ObjectType.DOCUMENT, "hello report", created_by="u:1",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:document:retr-0001"),
    )
    _save_indexed(repo, doc)

    SearchIndexApplier(session).apply_pending()
    session.commit()

    # global search (unchanged): finds BOTH the conversation and the document
    global_hits = SQLAlchemySearchRepository(session).search(text="hello", limit=10)
    global_ids = {h.object_id for h in global_hits}
    assert "obj:ai_conversation:retr-0001" in global_ids
    assert "obj:document:retr-0001" in global_ids

    # AI retrieval: only the document
    user = _user()
    search_uc = SearchObjectsUseCase(
        search_repository=SQLAlchemySearchRepository(session),
        object_repository=repo,
        permission_evaluator=ObjectPermissionEvaluator(),
        vector_repository=None,
        embedder=None,
    )
    from app.application.services.graph_runtime import GraphRuntimeService

    service = AssistantRetrievalService(
        search_uc, GraphRuntimeService(repo, ObjectPermissionEvaluator()),
        repository=repo,
    )
    result = service.retrieve("hello", user)

    ids = [i.object_id for i in result.items]
    assert "obj:ai_conversation:retr-0001" not in ids
    assert "obj:document:retr-0001" in ids
    assert all(i.object_type != "ai_conversation" for i in result.items)
