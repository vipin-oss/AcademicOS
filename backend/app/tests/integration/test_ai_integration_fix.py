"""V3 AI-integration fix — end-to-end through the REAL chat/stream path.

Reproduces the reported symptom ("AI is not configured" despite a configured +
reachable Ollama) and proves the fix:

- a REACHABLE provider (a real OpenAIProvider pointed at a fake Ollama via
  httpx.MockTransport) produces a real answer through ``/ai/chat/stream``;
- an UNREACHABLE provider returns ``available=False`` with
  ``unavailable_reason="provider_unreachable"`` — NOT "not configured";
- an UNCONFIGURED provider returns ``unavailable_reason="not_configured"``.

No network, no real model, no secrets.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.ai import get_ai_core
from app.api.dependencies.auth import get_current_user
from app.application.ai.config import AiConfigView
from app.application.ai.core import AiCore
from app.application.ai.providers.registry import ProviderRegistry
from app.application.dtos.ai import ProviderConfig
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.ai.llm.openai import OpenAIProvider
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
from app.main import app

API = "/api/v1/ai"


def _fake_ollama_handler(request: httpx.Request) -> httpx.Response:
    """A minimal Ollama OpenAI-compatible /v1/chat/completions response.

    Handles BOTH the non-streaming JSON shape and the streaming SSE shape so
    the real adapter's ``generate`` and ``stream`` paths both succeed.
    """
    assert request.url.path.endswith("/chat/completions")
    body = json.loads(request.content)
    assert body["model"] == "qwen2.5:1.5b"

    if body.get("stream"):
        sse = (
            'data: {"choices":[{"delta":{"content":"AcademicOS AI OK"},"finish_reason":null}]}\n\n'
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
            '"usage":{"prompt_tokens":4,"completion_tokens":3,"total_tokens":7}}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, content=sse.encode(), headers={"Content-Type": "text/event-stream"})

    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "model": "qwen2.5:1.5b",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "AcademicOS AI OK"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 4,
                "completion_tokens": 3,
                "total_tokens": 7,
            },
        },
    )


def _unreachable_handler(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused")


def _core_with_gateway(gateway) -> AiCore:
    return AiCore(
        registry=ProviderRegistry(),
        gateways={"local-ollama": gateway},
        config=AiConfigView(
            enabled=True,
            default_provider="local-ollama",
            default_model="qwen2.5:1.5b",
            temperature=0.0,
            max_tokens=2048,
            timeout_seconds=30.0,
            streaming_enabled=True,
            feature_flags={
                "chat": True,
                "rag": False, "memory": False,
                "agents": False, "document_understanding": False,
                "streaming": True, "summarization": False,
                "semantic_search": False, "qa": False,
                "enrichment": False, "related_documents": False,
            },
        ),
    )


@pytest.fixture()
def harness():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    def _override_db():
        yield session

    fake_user = UniversalObject.create(
        ObjectType.USER, "chat.test", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:chat-test-0001"),
    )
    session.add(ObjectModel(
        id=str(fake_user.id), object_type="user", title="chat.test",
        status="active", version=1, metadata_json=[],
        audit_json={"created_by": "system", "created_at": "2026-01-01T00:00:00+00:00"},
    ))
    session.commit()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _reachable_core() -> AiCore:
    cfg = ProviderConfig(
        provider_id="local-ollama", kind="openai", model="qwen2.5:1.5b",
        base_url="http://localhost:11434/v1",
    )
    gateway = OpenAIProvider(cfg, client=httpx.Client(transport=httpx.MockTransport(_fake_ollama_handler)))
    return _core_with_gateway(gateway)


def _unreachable_core() -> AiCore:
    cfg = ProviderConfig(
        provider_id="local-ollama", kind="openai", model="qwen2.5:1.5b",
        base_url="http://localhost:11434/v1",
    )
    gateway = OpenAIProvider(cfg, client=httpx.Client(transport=httpx.MockTransport(_unreachable_handler)))
    return _core_with_gateway(gateway)


def test_reachable_provider_answers_through_real_chat_stream(harness):
    app.dependency_overrides[get_ai_core] = _reachable_core
    with harness.stream(
        "POST", f"{API}/chat/stream", json={"message": "Reply with exactly: AcademicOS AI OK"}
    ) as resp:
        assert resp.status_code == 200
        body = resp.read().decode()
    # The completion event must report available=True (NOT "not configured").
    assert "event: completion" in body
    assert '"available": true' in body
    assert "AcademicOS AI OK" in body


def test_unreachable_provider_is_classified_not_not_configured(harness):
    app.dependency_overrides[get_ai_core] = _unreachable_core
    resp = harness.post(f"{API}/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["unavailable_reason"] == "provider_unreachable"
    # The answer must NOT be the "not configured" message.
    assert "not configured" not in data["answer"].lower()


def test_unconfigured_provider_is_classified_not_configured(harness):
    # A provider with no base_url -> AiNotConfiguredError at generate time.
    cfg = ProviderConfig(
        provider_id="local-ollama", kind="openai", model="qwen2.5:1.5b", base_url=""
    )
    gateway = OpenAIProvider(cfg)
    app.dependency_overrides[get_ai_core] = lambda: _core_with_gateway(gateway)
    resp = harness.post(f"{API}/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["unavailable_reason"] == "not_configured"


# ---------------------------------------------------------------------------
# Real-socket end-to-end: a real local TCP server stands in for Ollama, and the
# real OpenAIProvider (real httpx over real sockets) drives it — proving the
# actual network path that was previously failing ("endpoint unreachable").
# ---------------------------------------------------------------------------


class _OllamaStubHandler(BaseHTTPRequestHandler):
    """Minimal Ollama OpenAI-compatible /v1/chat/completions over real TCP."""

    model = "qwen2.5:1.5b"
    status_override = None  # set to e.g. 404 to simulate a missing model

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        if type(self).status_override is not None:
            self._send(status=type(self).status_override, payload={"error": "model not found"})
            return
        if body.get("stream"):
            sse = (
                'data: {"choices":[{"delta":{"content":"AcademicOS AI OK"},"finish_reason":null}]}\n\n'
                'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
                '"usage":{"prompt_tokens":4,"completion_tokens":3,"total_tokens":7}}\n\n'
                "data: [DONE]\n\n"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(sse.encode())))
            self.end_headers()
            self.wfile.write(sse.encode())
            return
        payload = {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "model": body.get("model", "qwen2.5:1.5b"),
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "AcademicOS AI OK"},
                 "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
        }
        self._send(status=200, payload=payload)

    def _send(self, *, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # silence per-request logging
        pass


@pytest.fixture()
def ollama_stub():
    """A real local Ollama stub server on an ephemeral IPv4 port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OllamaStubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def _real_gateway(server) -> OpenAIProvider:
    # The handler reads status_override from the CLASS; tests set it directly
    # (and reset it) around the call.
    port = server.server_address[1]
    cfg = ProviderConfig(
        provider_id="local-ollama", kind="openai", model="qwen2.5:1.5b",
        base_url=f"http://127.0.0.1:{port}/v1",
    )
    return OpenAIProvider(cfg, client=httpx.Client(timeout=10.0))


def test_real_socket_reachable_provider_answers(harness, ollama_stub):
    """The REAL network path: app -> OpenAIProvider -> real TCP -> stub -> answer."""
    _OllamaStubHandler.status_override = None
    app.dependency_overrides[get_ai_core] = lambda: _core_with_gateway(_real_gateway(ollama_stub))
    resp = harness.post(f"{API}/chat", json={"message": "Reply with exactly: AcademicOS AI OK"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["available"] is True
    assert data["answer"] == "AcademicOS AI OK"


def test_real_socket_model_unavailable_classified(harness, ollama_stub):
    """A real 404 (model not found) classifies as model_unavailable."""
    _OllamaStubHandler.status_override = 404
    app.dependency_overrides[get_ai_core] = lambda: _core_with_gateway(_real_gateway(ollama_stub))
    resp = harness.post(f"{API}/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["unavailable_reason"] == "model_unavailable"
    assert "not configured" not in data["answer"].lower()
    _OllamaStubHandler.status_override = None


def test_grounded_query_with_no_evidence_is_honest(harness, ollama_stub):
    """A grounded Hinglish query with NO data in the store must not fabricate
    evidence: the model is reached (available=True) but retrieved_count=0 and
    citations are empty — the honest no-evidence contract."""
    _OllamaStubHandler.status_override = None
    app.dependency_overrides[get_ai_core] = lambda: _core_with_gateway(_real_gateway(ollama_stub))
    resp = harness.post(
        f"{API}/chat",
        json={"message": "CBLU conference kab attend ki maine"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # The model answered (available) but NO evidence was retrieved or cited.
    assert data["available"] is True
    assert data["retrieved_count"] == 0
    assert data["citations"] == []
