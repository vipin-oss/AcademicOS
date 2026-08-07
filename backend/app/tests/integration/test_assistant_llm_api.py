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
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
    from app.domain.value_objects.vector import VectorDocument
    from app.infrastructure.persistence.mapper import SnapshotMapper
    from app.infrastructure.persistence.search_mapping import (
        search_text,
        to_search_document,
    )
    from app.infrastructure.search.index_applier import SearchIndexApplier

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


def _ask(client, question: str, conversation_id: str | None = None,
         model_id: str | None = None) -> dict:
    body = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    if model_id:
        body["model_id"] = model_id
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


def test_citations_over_http_reload_and_follow_up(harness):
    client, session, _, _ = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.domain.entities.object import UniversalObject as U
    from app.domain.value_objects.enums import ObjectType as OT

    doc = U.create(OT.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed(harness, doc)

    captured = _install_llm_chain(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": "answer"}}]}
        ),
        repo,
    )
    out = _ask(client, "find quantum")
    citations = out["answer"]["citations"]
    assert len(citations) == 1
    assert citations[0]["object_id"] == str(doc.id)
    assert citations[0]["number"] == 1
    assert captured["requests"][0]["citations"][0]["object_id"] == str(doc.id)
    assert out["answer"]["cards"]  # evidence cards rendered

    # Reload: citations reconstructed from the persisted answer.
    got = client.get(f"{API}/conversations/{out['conversation']['id']}").json()
    assert len(got["messages"][1]["answer"]["citations"]) == 1
    assert got["messages"][1]["answer"]["citations"][0]["object_id"] == str(doc.id)

    # Follow-up: citations remain stable (same retrieval, same numbering).
    second = _ask(client, "find quantum", conversation_id=out["conversation"]["id"])
    assert second["answer"]["citations"][0]["object_id"] == str(doc.id)
    assert second["answer"]["citations"][0]["number"] == 1
    assert second["conversation"]["message_count"] == 4


def test_restricted_object_never_cited_over_http(harness):
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
    assert all(c["object_id"] != str(secret.id) for c in out["answer"]["citations"])
    assert all("Secret" not in c["title"] for c in out["answer"]["citations"])
    assert all("Secret" not in c["title"] for c in out["answer"]["cards"])
    assert "Secret" not in captured["requests"][0]["messages"][1]["content"]


def test_ask_stream_sse_over_http(harness):
    """The SSE endpoint streams tokens then a completion whose stored answer
    matches the streamed text; reload confirms persistence."""
    client, session, _, _ = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.domain.entities.object import UniversalObject as U
    from app.domain.value_objects.enums import ObjectType as OT

    doc = U.create(OT.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed(harness, doc)
    _install_llm_chain(
        lambda request: httpx.Response(
            200,
            content=(
                b'data: {"choices": [{"delta": {"content": "Streamed"}}]}\n\n'
                b'data: {"choices": [{"delta": {"content": " answer"}}]}\n\n'
                b"data: [DONE]\n\n"
            ),
        ),
        repo,
    )

    res = client.post(f"{API}/ask/stream", json={"question": "find quantum"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    text = res.text
    assert "event: token" in text
    assert "Streamed" in text
    assert "answer" in text
    assert "event: completion" in text

    # The completion data mirrors the sync shape: verified citations,
    # evidence cards, persisted conversation.
    import re

    frames = re.findall(r"event: (\w+)\ndata: (.*?)\n\n", text, re.S)
    events = [name for name, _data in frames]
    assert events[-1] == "completion"
    completion_data = json.loads(frames[-1][1])
    assert completion_data["answer"]["summary"] == "Streamed answer"
    assert completion_data["answer"]["citations"][0]["object_id"] == str(doc.id)
    assert completion_data["answer"]["cards"]
    assert completion_data["conversation"]["message_count"] == 2

    # Reload: the stored message equals the streamed answer.
    conv_id = completion_data["conversation"]["id"]
    got = client.get(f"{API}/conversations/{conv_id}").json()
    assert got["messages"][1]["content"] == "Streamed answer"
    assert got["messages"][1]["answer"]["citations"][0]["object_id"] == str(doc.id)


def test_ask_stream_requires_auth_and_validates(harness):
    client, _, _, _ = harness
    app.dependency_overrides.pop(get_current_user, None)
    assert client.post(f"{API}/ask/stream", json={"question": "x"}).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: None  # restore marker
    app.dependency_overrides.clear()
    from app.domain.entities.object import UniversalObject as U
    from app.domain.value_objects.enums import ObjectStatus as OS

    fake = U.create(
        ObjectType.USER, "test.user", created_by="system", status=OS.ACTIVE,
        object_id=ObjectId(FAKE_USER),
    )
    app.dependency_overrides[get_current_user] = lambda: fake
    # Empty question -> 422.
    assert client.post(f"{API}/ask/stream", json={"question": ""}).status_code == 422


def test_review_workflow_sync_and_stream(harness):
    """With the review gate enabled, both sync and stream answers are
    stored PENDING, hidden from the conversation until approved, and stay
    hidden after rejection; the queue lists, approves and rejects."""
    import app.core.config as config_mod

    client, session, _, _ = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.domain.entities.object import UniversalObject as U
    from app.domain.value_objects.enums import ObjectType as OT

    doc = U.create(OT.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed(harness, doc)

    # Enable the review gate for this test (the route reads settings).
    original = config_mod.settings.assistant_review_enabled
    config_mod.settings.assistant_review_enabled = True
    try:
        _install_llm_chain(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": "Review me"}}]}
            ),
            repo,
        )
        # SYNC ask -> pending.
        out = _ask(client, "find quantum")
        conv_id = out["conversation"]["id"]
        assert out["conversation"]["version"] >= 1

        pending = client.get(f"{API}/review/pending").json()["items"]
        assert [p["conversation"]["id"] for p in pending] == [conv_id]
        assert pending[0]["question"] == "find quantum"
        assert pending[0]["answer"] == "Review me"

        # Hidden while pending.
        got = client.get(f"{API}/conversations/{conv_id}").json()
        assert got["messages"][1]["content"] == ""
        assert got["messages"][1]["answer"] is None

        # Approve -> visible with the full answer.
        appr = client.post(f"{API}/review/approve", json={"conversation_id": conv_id})
        assert appr.status_code == 200
        assert client.get(f"{API}/review/pending").json()["items"] == []
        got = client.get(f"{API}/conversations/{conv_id}").json()
        assert got["messages"][1]["content"] == "Review me"
        assert got["messages"][1]["answer"]["summary"] == "Review me"

        # Reject -> hidden again.
        rej = client.post(f"{API}/review/reject", json={"conversation_id": conv_id})
        assert rej.status_code == 200
        got = client.get(f"{API}/conversations/{conv_id}").json()
        assert got["messages"][1]["content"] == ""
        assert got["messages"][1]["answer"] is None

        # STREAM ask on the SAME conversation -> pending again (shared path).
        # Install a STREAMING handler so the LLM transport streams tokens.
        _install_llm_chain(
            lambda request: httpx.Response(
                200,
                content=(
                    b'data: {"choices": [{"delta": {"content": "Streamed"}}]}\n\n'
                    b'data: {"choices": [{"delta": {"content": " answer"}}]}\n\n'
                    b"data: [DONE]\n\n"
                ),
            ),
            repo,
        )
        res = client.post(f"{API}/ask/stream", json={
            "question": "tell me more", "conversation_id": conv_id,
        })
        assert res.status_code == 200
        assert "event: completion" in res.text
        pending = client.get(f"{API}/review/pending").json()["items"]
        assert [p["conversation"]["id"] for p in pending] == [conv_id]
        # Hidden again (the streamed answer is pending review).
        got = client.get(f"{API}/conversations/{conv_id}").json()
        assert got["messages"][-1]["content"] == ""
        assert got["messages"][-1]["answer"] is None

        # Approve the streamed answer -> the FULL streamed answer shows.
        client.post(f"{API}/review/approve", json={"conversation_id": conv_id})
        got = client.get(f"{API}/conversations/{conv_id}").json()
        assert got["messages"][-1]["content"] == "Streamed answer"
        assert got["messages"][-1]["answer"]["summary"] == "Streamed answer"
    finally:
        config_mod.settings.assistant_review_enabled = original


def test_review_duplicate_actions_and_unknown_404(harness):
    import app.core.config as config_mod

    client, session, _, _ = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.domain.entities.object import UniversalObject as U
    from app.domain.value_objects.enums import ObjectType as OT

    doc = U.create(OT.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed(harness, doc)
    original = config_mod.settings.assistant_review_enabled
    config_mod.settings.assistant_review_enabled = True
    try:
        _install_llm_chain(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": "A"}}]}
            ),
            repo,
        )
        out = _ask(client, "find quantum")
        conv_id = out["conversation"]["id"]

        # Duplicate approvals are idempotent (200, no error).
        assert client.post(f"{API}/review/approve", json={"conversation_id": conv_id}).status_code == 200
        assert client.post(f"{API}/review/approve", json={"conversation_id": conv_id}).status_code == 200
        # Duplicate rejections likewise.
        assert client.post(f"{API}/review/reject", json={"conversation_id": conv_id}).status_code == 200
        assert client.post(f"{API}/review/reject", json={"conversation_id": conv_id}).status_code == 200

        # Unknown conversation -> 404.
        ghost = str(ObjectId.generate(ObjectType.AI_CONVERSATION))
        assert client.post(f"{API}/review/approve", json={"conversation_id": ghost}).status_code == 404
        assert client.post(f"{API}/review/reject", json={"conversation_id": ghost}).status_code == 404
        assert client.get(f"{API}/review/pending").status_code == 200
    finally:
        config_mod.settings.assistant_review_enabled = original


def _selection_ai_core(client):
    """An AI Core with two OpenAI-compatible providers (main/alt) sharing a
    MockTransport client - the AI-Core authority for HTTP selection tests."""
    from app.application.ai.config import AiConfigView
    from app.application.ai.core import AiCore
    from app.application.ai.providers.registry import ProviderRegistry
    from app.application.dtos.ai import ProviderConfig
    from app.infrastructure.ai.llm.openai import OpenAIProvider

    def _gw(pid, model):
        return OpenAIProvider(
            ProviderConfig(provider_id=pid, kind="openai", model=model,
                           base_url="http://llm.example/v1"),
            client=client, retry_attempts=2, retry_backoff_seconds=0,
        )

    gateways = {"main": _gw("main", "model-main"), "alt": _gw("alt", "model-alt")}
    ai_cfg = AiConfigView(
        enabled=True, default_provider="main", default_model="",
        temperature=0.0, max_tokens=2048, timeout_seconds=30.0, streaming_enabled=True,
        feature_flags={"chat": False, "rag": False, "memory": False, "agents": False,
                       "document_understanding": False, "streaming": True},
    )
    return AiCore(registry=ProviderRegistry(), gateways=gateways,
                  config=ai_cfg, default_provider="main")


def test_model_selection_over_http_pin_override_invalid(harness):
    """AI-Core-driven selection over HTTP: the default provider is used and
    pinned; an override switches the provider and re-pins; an unknown model
    id returns 422 (sync and stream)."""
    client, session, _, _ = harness
    repo = SQLAlchemyObjectRepository(session)
    from app.domain.entities.object import UniversalObject as U
    from app.domain.value_objects.enums import ObjectType as OT

    doc = U.create(OT.DOCUMENT, "Quantum Paper", created_by="f:1")
    _seed(harness, doc)

    captured = {"models": []}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["models"].append(json.loads(request.content)["model"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    _client = httpx.Client(transport=httpx.MockTransport(handler))
    from app.api.dependencies.ai import get_ai_core

    ai_core = _selection_ai_core(_client)
    app.dependency_overrides[get_ai_core] = lambda: ai_core
    try:
        # 1. An explicit override selects the provider and pins the conversation.
        out = _ask(client, "find quantum", model_id="main")
        conv_id = out["conversation"]["id"]
        assert captured["models"] == ["model-main"]
        stored = repo.get_by_id(ObjectId(conv_id))
        assert stored.metadata.get_value("assistant.provider_id") == "main"

        # 2. Follow-up reuses the pin (same provider, no override needed).
        captured["models"].clear()
        _ask(client, "find quantum", conversation_id=conv_id)
        assert captured["models"] == ["model-main"]

        # 3. Override switches the provider and re-pins.
        captured["models"].clear()
        _ask(client, "find quantum", conversation_id=conv_id, model_id="alt")
        assert captured["models"] == ["model-alt"]
        stored = repo.get_by_id(ObjectId(conv_id))
        assert stored.metadata.get_value("assistant.provider_id") == "alt"

        # 4. Unknown model -> 422 (sync and stream).
        res = client.post(f"{API}/ask", json={
            "question": "find quantum", "conversation_id": conv_id, "model_id": "ghost",
        })
        assert res.status_code == 422
        res = client.post(f"{API}/ask/stream", json={
            "question": "find quantum", "conversation_id": conv_id, "model_id": "ghost",
        })
        assert res.status_code == 422
    finally:
        app.dependency_overrides.pop(get_ai_core, None)
