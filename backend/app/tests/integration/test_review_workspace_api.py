"""Integration tests for the review workspace API (Sprint-7 M5).

Full TestClient surface of the human feedback loop: approve/reject with
notes/rating/confidence/evaluation-run links (and the recorded decision
in the response), the per-conversation audit trail, the workspace feed,
the eval-run link validation (422 on unknown runs), feedback bounds (422
via pydantic), idempotent duplicate actions (200, audit rows appended),
the 401 gate, and backward compatibility of the conversation_id-only
body.

Mirrors ``test_assistant_api.py`` / ``test_eval_history_api.py``:
StaticPool in-memory SQLite, the app imported via ``pytest.importorskip``,
``get_db`` / ``get_current_user`` overridden, seeding done through the
REAL services (queue, evaluation history) the endpoints use.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.dependencies.auth import get_current_user  # noqa: E402
from app.application.dtos.assistant import AssistantAnswerOutput  # noqa: E402
from app.application.services.assistant_eval import (  # noqa: E402
    EvalResult,
    EvaluationHistory,
)
from app.application.services.assistant_review import AssistantReviewQueue  # noqa: E402
from app.application.use_cases.assistant.helpers import (  # noqa: E402
    append_message,
    create_conversation_object,
)
from app.domain.entities.object import UniversalObject  # noqa: E402
from app.domain.value_objects.enums import ObjectStatus, ObjectType  # noqa: E402
from app.domain.value_objects.object_id import ObjectId  # noqa: E402
from app.infrastructure.db.models.object_model import Base  # noqa: E402
from app.infrastructure.db.session import get_db  # noqa: E402
from app.infrastructure.persistence.eval_run_store import SQLEvalRunStore  # noqa: E402
from app.infrastructure.persistence.review_decision_store import (  # noqa: E402
    SQLReviewDecisionStore,
)
from app.infrastructure.repositories.sqlalchemy_object_repository import (  # noqa: E402
    SQLAlchemyObjectRepository,
)
from app.main import app  # noqa: E402

API = "/api/v1/assistant"


@pytest.fixture()
def harness():
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
    repo = SQLAlchemyObjectRepository(session)
    with TestClient(app) as client:
        yield client, repo, session
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _pending_conversation(repo) -> str:
    """A conversation with an assistant answer, awaiting review."""
    conv = create_conversation_object(repo, "New conversation", "u:1", title_auto=True)
    append_message(conv, "user", "find quantum", None)
    append_message(
        conv,
        "assistant",
        "The grounded answer.",
        AssistantAnswerOutput(
            intent="llm", intent_label="Assistant", question="find quantum",
            summary="The grounded answer.", sources=["llm"],
        ),
    )
    repo.save(conv)
    AssistantReviewQueue(repo).enqueue(str(conv.id))
    return str(conv.id)


def _seed_eval_run(session) -> str:
    run = EvaluationHistory(SQLEvalRunStore(session)).record_run(
        model_id="main",
        model_version="main-model",
        prompt_id="assistant.default",
        prompt_version=1,
        results=(EvalResult(name="a", passed=True),),
    )
    return run.run_id


# -------------------------------------------------------------------- auth
def test_review_workspace_requires_authentication(harness):
    client, _, _ = harness
    app.dependency_overrides.pop(get_current_user, None)
    assert client.get(f"{API}/review/decisions").status_code == 401
    assert client.get(f"{API}/review/decisions/obj:ai_conversation:1").status_code == 401
    assert client.post(f"{API}/review/approve", json={"conversation_id": "x"}).status_code == 401
    assert client.post(f"{API}/review/reject", json={"conversation_id": "x"}).status_code == 401


# ------------------------------------------------------------ approve
def test_approve_with_feedback_records_the_decision(harness):
    client, repo, session = harness
    conv_id = _pending_conversation(repo)
    run_id = _seed_eval_run(session)

    r = client.post(
        f"{API}/review/approve",
        json={
            "conversation_id": conv_id,
            "notes": "Well grounded and well cited.",
            "rating": 5,
            "confidence": 0.95,
            "eval_run_id": run_id,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["conversation"]["id"] == conv_id
    decision = body["decision"]
    assert decision["decision"] == "approved"
    assert decision["reviewer"] == "obj:user:test-user-0001"
    assert decision["notes"] == "Well grounded and well cited."
    assert decision["rating"] == 5
    assert decision["confidence"] == 0.95
    assert decision["eval_run_id"] == run_id
    assert decision["previous_status"] == "pending"
    assert decision["created_at"]
    # The answer became visible.
    got = client.get(f"{API}/conversations/{conv_id}").json()
    assert got["messages"][1]["content"] == "The grounded answer."
    assert client.get(f"{API}/review/pending").json()["items"] == []


def test_reject_with_feedback_hides_and_records(harness):
    client, repo, _ = harness
    conv_id = _pending_conversation(repo)

    r = client.post(
        f"{API}/review/reject",
        json={
            "conversation_id": conv_id,
            "notes": "Factual error in the summary.",
            "rating": 2,
            "confidence": 0.4,
        },
    )
    assert r.status_code == 200
    decision = r.json()["decision"]
    assert decision["decision"] == "rejected"
    assert decision["rating"] == 2
    assert decision["confidence"] == 0.4
    # The answer stays hidden.
    got = client.get(f"{API}/conversations/{conv_id}").json()
    assert got["messages"][1]["content"] == ""
    assert got["messages"][1]["answer"] is None


def test_approve_without_feedback_is_backward_compatible(harness):
    client, repo, _ = harness
    conv_id = _pending_conversation(repo)

    # The pre-M5 body shape keeps working and still records a decision
    # with defaults (reviewer = the authenticated user).
    r = client.post(f"{API}/review/approve", json={"conversation_id": conv_id})
    assert r.status_code == 200
    decision = r.json()["decision"]
    assert decision["decision"] == "approved"
    assert decision["reviewer"] == "obj:user:test-user-0001"
    assert decision["notes"] == ""
    assert decision["rating"] is None
    assert decision["confidence"] is None
    assert decision["eval_run_id"] is None


def test_feedback_bounds_are_enforced(harness):
    client, repo, _ = harness
    conv_id = _pending_conversation(repo)
    assert client.post(
        f"{API}/review/approve", json={"conversation_id": conv_id, "rating": 6}
    ).status_code == 422
    assert client.post(
        f"{API}/review/approve", json={"conversation_id": conv_id, "rating": 0}
    ).status_code == 422
    assert client.post(
        f"{API}/review/approve", json={"conversation_id": conv_id, "confidence": 1.5}
    ).status_code == 422
    assert client.post(
        f"{API}/review/approve", json={"conversation_id": conv_id, "notes": "x" * 2001}
    ).status_code == 422
    assert client.post(
        f"{API}/review/approve",
        json={"conversation_id": conv_id, "unexpected": "field"},
    ).status_code == 422


def test_unknown_eval_run_link_is_rejected(harness):
    client, repo, _ = harness
    conv_id = _pending_conversation(repo)
    r = client.post(
        f"{API}/review/approve",
        json={"conversation_id": conv_id, "eval_run_id": "no-such-run"},
    )
    assert r.status_code == 422
    assert "Unknown evaluation run" in r.json()["detail"]
    # Nothing was recorded and the state did not change.
    assert client.get(f"{API}/review/decisions/{conv_id}").json()["items"] == []
    assert len(client.get(f"{API}/review/pending").json()["items"]) == 1


def test_unknown_conversation_returns_404(harness):
    client, _, _ = harness
    r = client.post(
        f"{API}/review/approve", json={"conversation_id": "obj:ai_conversation:ghost"}
    )
    assert r.status_code == 404


def test_duplicate_approvals_and_rejections_stay_200_and_are_audited(harness):
    client, repo, _ = harness
    conv_id = _pending_conversation(repo)

    assert client.post(f"{API}/review/approve", json={"conversation_id": conv_id}).status_code == 200
    assert client.post(f"{API}/review/approve", json={"conversation_id": conv_id}).status_code == 200
    assert client.post(f"{API}/review/reject", json={"conversation_id": conv_id}).status_code == 200
    assert client.post(f"{API}/review/reject", json={"conversation_id": conv_id}).status_code == 200

    trail = client.get(f"{API}/review/decisions/{conv_id}").json()["items"]
    assert [d["decision"] for d in trail] == ["approved", "approved", "rejected", "rejected"]
    assert [d["previous_status"] for d in trail] == ["pending", "approved", "approved", "rejected"]


# ------------------------------------------------------- audit endpoints
def test_decisions_feed_is_newest_first_across_conversations(harness):
    client, repo, _ = harness
    first = _pending_conversation(repo)
    second = _pending_conversation(repo)
    client.post(f"{API}/review/approve", json={"conversation_id": first})
    client.post(f"{API}/review/reject", json={"conversation_id": second})

    feed = client.get(f"{API}/review/decisions").json()["items"]
    assert [d["decision"] for d in feed] == ["rejected", "approved"]
    assert feed[0]["conversation_id"] == second
    assert feed[1]["conversation_id"] == first
    assert [d["reviewer"] for d in feed] == ["obj:user:test-user-0001"] * 2

    bounded = client.get(f"{API}/review/decisions", params={"limit": 1}).json()["items"]
    assert len(bounded) == 1 and bounded[0]["conversation_id"] == second
    assert client.get(f"{API}/review/decisions", params={"limit": 0}).status_code == 422
    assert client.get(f"{API}/review/decisions", params={"limit": 101}).status_code == 422


def test_per_conversation_trail_is_chronological(harness):
    client, repo, _ = harness
    conv_id = _pending_conversation(repo)
    client.post(f"{API}/review/approve", json={"conversation_id": conv_id})
    client.post(f"{API}/review/reject", json={"conversation_id": conv_id})

    trail = client.get(f"{API}/review/decisions/{conv_id}").json()["items"]
    assert [d["decision"] for d in trail] == ["approved", "rejected"]
    # Never-reviewed conversations have an empty (not 404) trail.
    untouched = _pending_conversation(repo)
    assert client.get(f"{API}/review/decisions/{untouched}").json()["items"] == []
