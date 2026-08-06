"""Integration tests for the Academic Intelligence Assistant API.

Full TestClient surface: AI Home payload, the ask loop (create-on-first-ask,
append, validation 422s, 404s), the conversation CRUD surface (PUT+PATCH
twins, pinned ordering, pagination, delete), and the provider seam — the
``get_assistant_provider`` dependency is overridden with a stub to prove the
future-LLM swap point works at the route layer with zero route changes.

Mirrors ``test_settings_api.py``: StaticPool in-memory SQLite, the app
imported via ``pytest.importorskip``.
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.object_id import ObjectId
from app.api.dependencies.auth import get_current_user

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.infrastructure.db.models.object_model import Base  # noqa: E402
from app.infrastructure.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
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

    app.dependency_overrides[get_db] = _override_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:test-user-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1/assistant"


# ---------------------------------------------------------------------------
# AI Home & suggested catalogue
# ---------------------------------------------------------------------------
def test_home_empty_bootstrap(client: TestClient):
    r = client.get(f"{API}/home")
    assert r.status_code == 200
    home = r.json()
    assert home["conversation_count"] == 0
    assert home["recent"] == [] and home["pinned"] == []
    assert len(home["suggested"]) == 32
    sample = home["suggested"][0]
    assert set(sample) == {"group", "question", "intent"}


def test_suggested_catalogue_taxonomy(client: TestClient):
    r = client.get(f"{API}/suggested")
    assert r.status_code == 200
    data = r.json()
    assert len(data["suggested"]) == 32
    groups = [g["group"] for g in data["intents"]]
    assert groups == ["Dashboard", "Research", "Teaching", "Finance",
                      "Events", "Committees", "Reports", "Search"]
    codes = [code["code"] for g in data["intents"] for code in g["codes"]]
    assert len(codes) == 34 == len(set(codes))  # the whole taxonomy, unique
    assert all(code["label"] for g in data["intents"] for code in g["codes"])


# ---------------------------------------------------------------------------
# Ask loop
# ---------------------------------------------------------------------------
def test_ask_creates_conversation_with_answer(client: TestClient):
    r = client.post(f"{API}/ask", json={"question": "What should I do today?"})
    assert r.status_code == 201
    out = r.json()
    conv = out["conversation"]
    assert conv["title"] == "What should I do today?"  # auto-derived
    assert conv["message_count"] == 2
    assert conv["pinned"] is False
    assert out["user_message"]["role"] == "user"
    assert out["assistant_message"]["role"] == "assistant"
    answer = out["answer"]
    assert answer["intent"] == "today_plan"
    assert answer["intent_label"]
    assert set(answer) == {"intent", "intent_label", "question", "summary",
                           "metrics", "items", "cards", "actions", "sources",
                           "citations"}  # S6 M3 additive evidence field
    assert answer["metrics"]["Tasks due today"].isdigit()
    for card in answer["cards"]:
        assert card["href"] and card["object_type"] and card["title"]


def test_ask_appends_to_existing_conversation(client: TestClient):
    first = client.post(f"{API}/ask", json={"question": "hello"}).json()
    cid = first["conversation"]["id"]
    r = client.post(f"{API}/ask", json={"question": "upcoming deadlines",
                                        "conversation_id": cid})
    assert r.status_code == 201
    out = r.json()
    assert out["conversation"]["id"] == cid
    assert out["conversation"]["message_count"] == 4
    assert out["user_message"]["seq"] == 3
    assert out["assistant_message"]["seq"] == 4
    detail = client.get(f"{API}/conversations/{cid}").json()
    assert len(detail["messages"]) == 4
    assert detail["messages"][1]["answer"]["intent"] == "greeting"
    assert detail["messages"][3]["answer"]["intent"] == "upcoming_deadlines"


def test_ask_unknown_conversation_is_404(client: TestClient):
    r = client.post(f"{API}/ask",
                    json={"question": "hi", "conversation_id": "obj:ai_conversation:ZZZZ"})
    assert r.status_code == 404


def test_ask_cross_module_grounding(client: TestClient):
    r = client.post(f"{API}/ask", json={"question": "What reports can I see?"})
    answer = r.json()["answer"]
    assert answer["intent"] == "report_catalogue"
    assert answer["metrics"]["Report kinds"] == "9"
    hrefs = {card["href"] for card in answer["cards"]}
    assert "/reports/publications" in hrefs and "/reports/analytics" in hrefs
    assert any(action["href"] == "/reports" for action in answer["actions"])
    empty = client.post(f"{API}/ask", json={"question": "Show my publications"}).json()["answer"]
    assert empty["intent"] == "my_publications"
    assert empty["metrics"]["Publications"] == "0"  # honest empty world


def test_ask_validation_errors(client: TestClient):
    assert client.post(f"{API}/ask", json={"question": "   "}).status_code == 422
    assert client.post(f"{API}/ask", json={"question": "x" * 501}).status_code == 422
    assert client.post(f"{API}/ask", json={"question": "hi", "conversation_id": " "}).status_code == 422
    assert client.post(f"{API}/ask", json={"question": "hi", "bogus": 1}).status_code == 422
    assert client.post(f"{API}/ask", json={}).status_code == 422


def test_provider_seam_override_at_route_layer(client: TestClient):
    """The future-LLM swap point: overriding ONE dependency swaps the engine
    without touching routes, use cases, or the answer contract."""
    from app.api.routes.assistant import get_assistant_provider

    class StubProvider:
        @property
        def name(self):
            return "stub-v0"

        def answer(self, question, asked_by):
            from app.application.dtos.assistant import AssistantAnswerOutput
            return AssistantAnswerOutput(
                intent="stub", intent_label="Stub", question=question,
                summary=f"canned:{question}", sources=["stub"],
            )

    app.dependency_overrides[get_assistant_provider] = lambda: StubProvider()
    try:
        r = client.post(f"{API}/ask", json={"question": "quantum entanglement"})
        assert r.status_code == 201
        assert r.json()["answer"]["summary"] == "canned:quantum entanglement"
    finally:
        app.dependency_overrides.pop(get_assistant_provider, None)


# ---------------------------------------------------------------------------
# Conversation CRUD (PUT+PATCH twins, pinned ordering, pagination, delete)
# ---------------------------------------------------------------------------
def test_conversation_create_get_update_delete(client: TestClient):
    created = client.post(f"{API}/conversations", json={"title": "Deep dive"})
    assert created.status_code == 201
    conv = created.json()
    assert conv["title"] == "Deep dive" and conv["pinned"] is False
    cid = conv["id"]

    detail = client.get(f"{API}/conversations/{cid}")
    assert detail.status_code == 200
    assert detail.json()["messages"] == []

    renamed = client.put(f"{API}/conversations/{cid}", json={"title": "Renamed"})
    assert renamed.status_code == 200 and renamed.json()["title"] == "Renamed"
    pinned = client.patch(f"{API}/conversations/{cid}", json={"pinned": True})
    assert pinned.status_code == 200 and pinned.json()["pinned"] is True
    both = client.patch(f"{API}/conversations/{cid}",
                        json={"title": "Renamed again", "pinned": False})
    assert both.json()["title"] == "Renamed again" and both.json()["pinned"] is False

    assert client.delete(f"{API}/conversations/{cid}").status_code == 204
    assert client.get(f"{API}/conversations/{cid}").status_code == 404


def test_conversation_update_validation(client: TestClient):
    cid = client.post(f"{API}/conversations", json={}).json()["id"]
    assert client.put(f"{API}/conversations/{cid}", json={}).status_code == 422  # nothing
    assert client.put(f"{API}/conversations/{cid}", json={"title": "x" * 121}).status_code == 422
    assert client.put(f"{API}/conversations/{cid}", json={"pinned": "yes"}).status_code == 422
    assert client.put(f"{API}/conversations/{cid}", json={"extra": 1}).status_code == 422
    assert client.put(f"{API}/conversations/nope", json={"pinned": True}).status_code == 404
    assert client.post(f"{API}/conversations", json={"title": "  "}).status_code == 422
    assert client.post(f"{API}/conversations", json={"weird": 1}).status_code == 422


def test_title_reset_to_auto(client: TestClient):
    asked = client.post(f"{API}/ask", json={"question": "budget remaining"}).json()
    cid = asked["conversation"]["id"]
    client.put(f"{API}/conversations/{cid}", json={"title": "Money matters"})
    reset = client.put(f"{API}/conversations/{cid}", json={"title": ""})
    assert reset.status_code == 200
    assert reset.json()["title"] == "budget remaining"  # re-derived


def test_list_pinned_first_and_pagination(client: TestClient):
    one = client.post(f"{API}/ask", json={"question": "hello"}).json()["conversation"]["id"]
    client.post(f"{API}/ask", json={"question": "upcoming events"})
    client.post(f"{API}/ask", json={"question": "certificates"})
    listing = client.get(f"{API}/conversations").json()
    assert listing["total_count"] == 3
    client.patch(f"{API}/conversations/{one}", json={"pinned": True})
    listing = client.get(f"{API}/conversations").json()
    assert listing["items"][0]["id"] == one  # pinned floats to the top
    page2 = client.get(f"{API}/conversations", params={"page": 2, "page_size": 2}).json()
    assert page2["page"] == 2 and len(page2["items"]) == 1
    assert client.get(f"{API}/conversations", params={"page_size": 0}).status_code == 422
    assert client.get(f"{API}/conversations", params={"page_size": 101}).status_code == 422


def test_home_reflects_activity(client: TestClient):
    asked = client.post(f"{API}/ask", json={"question": "certificates"}).json()
    cid = asked["conversation"]["id"]
    client.patch(f"{API}/conversations/{cid}", json={"pinned": True})
    home = client.get(f"{API}/home").json()
    assert home["conversation_count"] == 1
    assert [c["id"] for c in home["recent"]] == [cid]
    assert [c["id"] for c in home["pinned"]] == [cid]


def test_health_regression_and_openapi_tags(client: TestClient):
    assert client.get("/api/v1/health").status_code == 200
    openapi = client.get("/openapi.json").json()
    assistant_paths = [p for p in openapi["paths"] if p.startswith("/api/v1/assistant")]
    assert len(assistant_paths) == 5  # home / ask / suggested / conversations / {id}
