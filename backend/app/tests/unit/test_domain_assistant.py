"""Unit tests: Domain Assistant use case (Sprint M22-M25 — Group D, F18-F21).

Covers the role catalogue (F18-F21), the teaching academic-integrity guard
(F19.3 / A11 — minimal deterministic slice), and that non-teaching roles
delegate to the shared grounded pipeline (no duplication of grounding logic).
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from app.application.dtos.ai import QAResult
from app.application.use_cases.ai.chat import ChatTurn
from app.application.use_cases.ai.domain_assistant import (
    ASSISTANT_ROLES,
    ASSISTANT_ROLE_KEYS,
    DomainAssistantUseCase,
    detect_assessable_completion,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId


class _StubGrounded:
    """Minimal stand-in for GroundedQAUseCase: records calls, returns a marker."""

    def __init__(self, result: QAResult | None = None, *, raise_on_call: bool = False):
        self.calls: list[tuple] = []
        self._result = result or QAResult(answer="GROUND-RESPONSE", available=True)
        self._raise = raise_on_call

    def execute(self, question, user, *, conversation=None):
        self.calls.append(("execute", question, conversation))
        if self._raise:
            raise AssertionError("grounded pipeline must NOT be called for a refused message")
        return self._result

    def stream(self, question, user, *, conversation=None):
        self.calls.append(("stream", question, conversation))
        if self._raise:
            raise AssertionError("grounded pipeline must NOT stream for a refused message")
        yield {"type": "complete", "result": self._result}


@pytest.fixture()
def user() -> UniversalObject:
    return UniversalObject.create(
        ObjectType.USER, "asst.test", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:asst-unit-0000001"),
    )


class TestRoleCatalogue:
    def test_four_roles_present(self):
        assert set(ASSISTANT_ROLE_KEYS) == {"research", "teaching", "publication", "administration"}

    def test_each_role_has_distinct_prompt_and_instructions(self):
        prompts = {r.prompt_id for r in ASSISTANT_ROLES.values()}
        instructions = {r.system_instructions for r in ASSISTANT_ROLES.values()}
        assert len(prompts) == 4
        assert len(instructions) == 4

    def test_administration_role_is_proposal_only(self):
        # F21 duty of care: the admin assistant must frame output as proposals.
        text = ASSISTANT_ROLES["administration"].system_instructions
        assert "PROPOSE" in text or "DRAFT" in text
        assert "approval" in text.lower()

    def test_publication_role_forbids_fabrication(self):
        text = ASSISTANT_ROLES["publication"].system_instructions
        assert "do not invent" in text.lower()

    def test_research_role_marks_hypotheses(self):
        text = ASSISTANT_ROLES["research"].system_instructions
        assert "hypothesis" in text.lower()


class TestTeachingIntegrityGuard:
    @pytest.mark.parametrize(
        "message",
        [
            "write my essay on photosynthesis",
            "please do my homework for me",
            "solve this assignment for me",
            "give me the answers to quiz 3",
            "write my lab report",
            "DO MY ASSIGNMENT",  # case-insensitive
        ],
    )
    def test_detects_assessable_completion(self, message):
        assert detect_assessable_completion(message) is True

    @pytest.mark.parametrize(
        "message",
        [
            "explain photosynthesis at an introductory level",
            "give me three practice questions on mitosis",
            "outline a lesson plan for week 4",
            "review my draft essay and tell me how to improve it",
            "what is the difference between mitosis and meiosis",
            "quiz me on chapter 5",
        ],
    )
    def test_legit_teaching_requests_not_flagged(self, message):
        assert detect_assessable_completion(message) is False

    def test_teaching_short_circuits_without_gateway(self, user):
        """An assessable-completion request never reaches the gateway."""
        grounded = _StubGrounded(raise_on_call=True)
        use_case = DomainAssistantUseCase(grounded, ASSISTANT_ROLES["teaching"])
        result = use_case.execute("write my essay for me", None, user)
        assert result.available is True  # it IS responding (a refusal), not an error
        assert result.citations == ()
        assert "can't" in result.answer.lower() or "cannot" in result.answer.lower()
        assert grounded.calls == []  # gateway never invoked

    def test_teaching_legit_request_delegates_to_grounded(self, user):
        grounded = _StubGrounded()
        use_case = DomainAssistantUseCase(grounded, ASSISTANT_ROLES["teaching"])
        result = use_case.execute("explain mitosis", None, user)
        assert result.answer == "GROUND-RESPONSE"
        assert len(grounded.calls) == 1
        assert grounded.calls[0][0] == "execute"

    def test_teaching_stream_refusal_single_completion(self, user):
        grounded = _StubGrounded(raise_on_call=True)
        use_case = DomainAssistantUseCase(grounded, ASSISTANT_ROLES["teaching"])
        events = list(use_case.stream("do my homework", None, user))
        assert len(events) == 1
        assert events[0]["type"] == "complete"
        assert events[0]["result"].available is True
        assert grounded.calls == []


class TestNonTeachingDelegation:
    @pytest.mark.parametrize("role_key", ["research", "publication", "administration"])
    def test_delegates_to_grounded(self, role_key, user):
        grounded = _StubGrounded()
        use_case = DomainAssistantUseCase(grounded, ASSISTANT_ROLES[role_key])
        result = use_case.execute("summarize the gap", None, user)
        assert result.answer == "GROUND-RESPONSE"
        assert len(grounded.calls) == 1

    def test_history_carried_into_conversation(self, user):
        """Prior turns are folded into a transient conversation (M15 stateless pattern)."""
        grounded = _StubGrounded()
        use_case = DomainAssistantUseCase(grounded, ASSISTANT_ROLES["research"])
        history = [ChatTurn("user", "prior question"), ChatTurn("assistant", "prior answer")]
        use_case.execute("follow up", history, user)
        _, _, conversation = grounded.calls[0]
        assert conversation is not None
        assert conversation.object_type == ObjectType.AI_CONVERSATION

    @pytest.mark.parametrize("role_key", ["research", "publication", "administration"])
    def test_never_applies_integrity_guard(self, role_key, user):
        """Non-teaching roles must NOT intercept assessable phrasing."""
        grounded = _StubGrounded()
        use_case = DomainAssistantUseCase(grounded, ASSISTANT_ROLES[role_key])
        use_case.execute("write my essay", None, user)
        assert len(grounded.calls) == 1  # delegated, not refused
