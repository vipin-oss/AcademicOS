"""Integration tests: the production LLM provider over HTTP (Sprint-6 M2).

The route's provider chain (LLM transport + deterministic rules fallback)
is exercised end-to-end with an httpx.MockTransport wire: LLM success is
persisted, LLM failure degrades to the rules fallback without crashing,
and restricted objects never reach the LLM prompt.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.api.routes.assistant import get_assistant_provider
from app.api.routes.search import get_embedder, get_vector_repository
from app.application.assistant.providers import (
    FallbackAssistantProvider,
    RuleBasedAssistantProvider,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.infrastructure.llm.llm_provider import LlmAssistantProvider
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.vector_db.fake import FakeVectorRepository
from app.main import app

API = "/api/v1/assistant"
FAKE_USER = "obj:user:test-user-0001"


@pytest.fixture()
def harness(tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId(FAKE_USER),
    )
    session.add(
        ObjectModel(
            id=str(fake_user.id), object_type="user", title="test.user",
            status="active", version=1, metadata_json=[],
            audit_json={"created_by": "system", "created_at": "2026-01-01T00:00:00+00:00"},
        )
    )
    session.commit()
    vectors = FakeVectorRepository()
    embedder = HashingEmbedder()
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_vector_repository] = lambda: vectors
    app.dependency_overrides[get_embedder] = lambda: embedder
    with TestClient(app) as client:
        yield client, session, vectors, embedder
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _install_llm_chain(handler, repo) -> dict:
    """Override the provider seam with LLM transport + rules fallback."""
    captured = {"requests": []}

    def wrapped_handler(request: httpx.Request) -> httpx.Response:
        captured["requests"].append(json.loads(request.content))
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(wrapped_handler))
    primary = LlmAssistantProvider(
        client, model="test-model", base_url="http://llm.example",
        retry_attempts=2, retry_backoff_seconds=0,
    )
    fallback = RuleBasedAssistantProvider(
        repo, permission_evaluator=ObjectPermissionEvaluator()
    )
    app.dependency_overrides[get_assistant_provider] = lambda: FallbackAssistantProvider(
        primary, fallback
    )
    return captured


def _seed(harness, *objects) -> None:
    client, session, vectors, embedder = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.application.services.outbox import to_outbox_row
    from app.infrastructure.persistence.mapper import SnapshotMapper
    from app.infrastructure.persistence.search_mapping import (
        search_text,
        to_search_document,
    )
    from app.infrastructure.search.index_applier import SearchIndexApplier
    from app.domain.value_objects.vector import VectorDocument

    for obj in objects:
        events = obj.pop_domain_events()
        repo.save(obj, outbox_events=[to_outbox_row(e) for e in events])
    SearchIndexApplier(session).apply_pending()
    for obj in objects:
        snap = SnapshotMapper.to_snapshot(obj)
        d = to_search_document(snap)
        vectors.upsert(
            VectorDocument(
                object_id=d.object_id, object_type=d.object_type, title=d.title,
                metadata_text=d.metadata_text, version=d.version,
                vector=tuple(embedder.embed(search_text(snap))),
            )
        )


def _ask(client, question: str, conversation_id: str | None = None) -> dict:
    body = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    res = client.post(f"{API}/ask", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_llm_success_flow_over_http(harness):
    client, session, _, _ = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.domain.entities.object import UniversalObject as U
    from app.domain.value_objects.enums import ObjectType as OT

    doc = U.create(OT.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed(harness, doc)

    captured = _install_llm_chain(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": "LLM summary over HTTP."}}]}
        ),
        repo,
    )
    out = _ask(client, "find quantum")
    assert out["answer"]["summary"] == "LLM summary over HTTP."
    assert out["answer"]["intent"] == "llm"
    assert out["conversation"]["message_count"] == 2
    # The prompt carried the provenance section.
    assert "RETRIEVED CONTEXT" in captured["requests"][0]["messages"][1]["content"]
    # Reload: the LLM answer persisted.
    got = client.get(f"{API}/conversations/{out['conversation']['id']}").json()
    assert got["conversation"]["message_count"] == 2
    assert got["messages"][1]["answer"]["summary"] == "LLM summary over HTTP."


def test_llm_failure_falls_back_over_http(harness):
    client, session, _, _ = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.domain.entities.object import UniversalObject as U
    from app.domain.value_objects.enums import ObjectType as OT

    doc = U.create(OT.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed(harness, doc)

    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _install_llm_chain(failing_handler, repo)
    out = _ask(client, "find quantum")
    # Deterministic fallback answered; conversation still persisted.
    assert out["answer"]["summary"]
    assert out["conversation"]["message_count"] == 2
    assert out["answer"]["intent"] != "llm"

    # Follow-up on the SAME conversation still works.
    second = _ask(client, "tell me more", conversation_id=out["conversation"]["id"])
    assert second["conversation"]["message_count"] == 4


def test_restricted_object_never_reaches_the_llm_over_http(harness):
    client, session, _, _ = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.domain.entities.object import UniversalObject as U
    from app.domain.value_objects.enums import ObjectType as OT

    public = U.create(OT.DOCUMENT, "Quantum Public", created_by="f:1")
    secret = U.create(OT.DOCUMENT, "Quantum Secret", created_by="f:2")
    secret.set_metadata(
        MetadataEntry(
            "acl.readers", json.dumps(["obj:user:someone-else"]),
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    _seed(harness, public, secret)

    captured = _install_llm_chain(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        ),
        repo,
    )
    out = _ask(client, "find quantum")
    prompt = captured["requests"][0]["messages"][1]["content"]
    assert "Quantum Public" in prompt
    assert "Secret" not in prompt  # permission filter precedes the prompt
    assert out["answer"]["summary"] == "ok"
