"""Unit tests for the Assistant Context Builder (Sprint-6 M1 Phase 2).

History + retrieval are combined into one bounded envelope: provenance is
preserved, ordering is deterministic, budgets are enforced, and trimming
always drops the OLDEST content first.
"""
from __future__ import annotations

from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.dtos.assistant import (
    AssistantRetrievalResult,
    RetrievedItem,
)
from app.application.use_cases.assistant.helpers import append_message
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType


def _conversation() -> UniversalObject:
    return UniversalObject.create(
        ObjectType.AI_CONVERSATION, "New conversation", created_by="u:1",
        status=ObjectStatus.ACTIVE,
    )


def _item(object_id: str, title: str) -> RetrievedItem:
    return RetrievedItem(
        object_id=object_id,
        object_type="document",
        title=title,
        version=1,
        sources=("search",),
        score=0.1,
    )


def _retrieval(*items: RetrievedItem) -> AssistantRetrievalResult:
    return AssistantRetrievalResult(items=tuple(items), search_count=len(items), graph_count=0)


def test_build_with_history_and_retrieval():
    conv = _conversation()
    append_message(conv, "user", "What is quantum physics?", None)
    append_message(conv, "assistant", "A branch of physics.", None)

    context = AssistantContextBuilder().build(
        conv, "Tell me more", _retrieval(_item("obj:document:A", "Quantum Paper"))
    )
    assert [role for role, _c in context.history] == ["user", "assistant"]
    assert context.history[0][1] == "What is quantum physics?"
    assert [r.object_id for r in context.retrieved] == ["obj:document:A"]
    assert context.question == "Tell me more"
    assert context.truncated is False


def test_build_without_conversation():
    context = AssistantContextBuilder().build(
        None, "First question", _retrieval(_item("obj:document:A", "Doc"))
    )
    assert context.history == ()
    assert len(context.retrieved) == 1


def test_build_without_retrieval():
    conv = _conversation()
    append_message(conv, "user", "hello", None)
    context = AssistantContextBuilder().build(conv, "hi", None)
    assert context.retrieved == ()
    assert len(context.history) == 1


def test_history_preserves_deterministic_order():
    conv = _conversation()
    for i in range(5):
        append_message(conv, "user", f"q{i}", None)
        append_message(conv, "assistant", f"a{i}", None)
    context = AssistantContextBuilder().build(conv, "next", None)
    contents = [content for _role, content in context.history]
    assert contents == [item for i in range(5) for item in (f"q{i}", f"a{i}")]


def test_history_trims_oldest_first():
    conv = _conversation()
    for i in range(10):
        append_message(conv, "user", f"question number {i}", None)
        append_message(conv, "assistant", f"answer number {i}", None)
    # Tiny history budget: only the newest tail survives.
    context = AssistantContextBuilder(history_budget=60).build(conv, "next", None)
    assert context.truncated is True
    # The oldest messages were dropped; the tail is the newest content.
    contents = [c for _r, c in context.history]
    assert "question number 0" not in contents
    assert "question number 9" in contents  # the newest pair survives


def test_retrieval_trims_to_remaining_budget():
    items = [_item(f"obj:document:{i:02d}", f"Document {i}") for i in range(20)]
    context = AssistantContextBuilder(
        context_budget=200, history_budget=10
    ).build(_conversation(), "q", _retrieval(*items))
    assert len(context.retrieved) < len(items)
    assert context.truncated is True
    # The deterministic order is preserved: first items kept, tail trimmed.
    assert context.retrieved[0].object_id == "obj:document:00"


def test_provenance_is_preserved():
    both = RetrievedItem(
        object_id="obj:document:B", object_type="document", title="Both",
        version=2, sources=("search", "graph"), score=0.5,
    )
    context = AssistantContextBuilder().build(
        None, "q", _retrieval(_item("obj:document:A", "Search"), both)
    )
    assert context.retrieved[1].sources == ("search", "graph")
    assert context.retrieved[1].score == 0.5


def test_budget_is_deterministic_across_builds():
    conv = _conversation()
    for i in range(8):
        append_message(conv, "user", f"message {i}", None)
    builder = AssistantContextBuilder(history_budget=60)
    first = builder.build(conv, "q", None)
    second = builder.build(conv, "q", None)
    assert first.history == second.history
    assert first.truncated == second.truncated
