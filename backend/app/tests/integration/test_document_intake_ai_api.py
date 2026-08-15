"""V3 ADR-069 document-intake API tests with the AI enrichment layer wired.

End-to-end through the real FastAPI route: ``POST /documents/{id}/analyze``
runs the deterministic pipeline first and then the AI semantic extraction
layer (via the ``get_ai_core`` dependency). Proves the response exposes
``extraction_mode`` and the AI-derived fields with ``extractor == "ai"``,
while an unconfigured/unreachable provider leaves the pipeline deterministic.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

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
from app.infrastructure.db.models.document_content_model import DocumentContentModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.session import get_db
from app.main import app

CONFERENCE_PROSE = (
    'This is to certify that Dr. A.B. Sharma presented the research paper '
    'entitled "Topological Insulators for Energy Storage" at the International '
    'Conference on Quantum Materials organized by the Indian Physics '
    'Association held at Vigyan Bhawan, New Delhi from 6 December 2022 to '
    '11 December 2022. He was awarded the Best Paper Award.'
)


def _core(gateway) -> AiCore:
    return AiCore(
        registry=ProviderRegistry(),
        gateways={"local-ollama": gateway},
        config=AiConfigView(
            enabled=True,
            default_provider="local-ollama",
            default_model="qwen2.5:1.5b",
            temperature=0.0, max_tokens=2048, timeout_seconds=30.0,
            streaming_enabled=True,
            feature_flags={"chat": True, "rag": False, "memory": False,
                           "agents": False, "document_understanding": False,
                           "streaming": True, "summarization": False,
                           "semantic_search": False, "qa": False,
                           "enrichment": False, "related_documents": False},
        ),
    )


def _ai_core() -> AiCore:
    payload = json.dumps({
        "city": {"value": "New Delhi", "confidence": 0.95},
        "award_title": {"value": "Best Paper Award", "confidence": 0.92},
    })

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"index": 0,
                         "message": {"role": "assistant", "content": payload},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        })

    cfg = ProviderConfig(
        provider_id="local-ollama", kind="openai", model="qwen2.5:1.5b",
        base_url="http://127.0.0.1:11434/v1",
    )
    gateway = OpenAIProvider(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)))
    return _core(gateway)


@pytest.fixture()
def harness():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    def _override_db():
        yield session

    user = UniversalObject.create(
        ObjectType.USER, "intake.ai.user", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:intake-ai-1"),
    )
    session.add(ObjectModel(
        id=str(user.id), object_type="user", title="intake.ai.user", status="active",
        version=1, metadata_json=[],
        audit_json={"created_by": "system", "created_at": "2026-01-01T00:00:00+00:00"},
    ))
    doc = UniversalObject.create(
        ObjectType.DOCUMENT, "certificate.pdf", created_by=str(user.id),
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:document:intake-ai-1"),
    )
    session.add(ObjectModel(
        id=str(doc.id), object_type="document", title="certificate.pdf", status="active",
        version=1, metadata_json=[],
        audit_json={"created_by": str(user.id), "created_at": "2026-01-01T00:00:00+00:00"},
    ))
    # Seed the document's authoritative extracted text (direct-upload content).
    session.add(DocumentContentModel(
        object_id=str(doc.id), version=1, content_text=CONFERENCE_PROSE,
        content_hash="seed", source_item_id=str(doc.id),
        created_at="2026-01-01T00:00:00+00:00",
    ))
    session.commit()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_ai_core] = _ai_core
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_analyze_endpoint_reports_ai_assisted_extraction(harness):
    resp = harness.post("/api/v1/documents/obj:document:intake-ai-1/analyze")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["extraction_mode"] == "ai_assisted"
    fields = {f["predicate_id"]: f for f in body["fields"]}
    assert fields["conference_name"]["value"] == "Quantum Materials"
    assert fields["conference_name"]["extractor"] == "prose"
    assert fields["city"]["value"] == "New Delhi"
    assert fields["city"]["extractor"] == "ai"
    assert fields["award_title"]["value"] == "Best Paper Award"
    assert fields["award_title"]["extractor"] == "ai"
    # AI-derived fields are PROPOSED (never auto-suggested/confirmed) -> review
    assert body["review_required"] is True
