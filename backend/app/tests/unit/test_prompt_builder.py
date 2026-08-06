"""Unit tests for the Prompt Builder (Sprint-6 M2 Phase 3).

The single owner of prompt construction: deterministic formatting, history
+ provenance + question sections, system instructions, injection-safety
delimiters, and a hard token-budget cap that drops the retrieval tail
first — never the question.
"""
from __future__ import annotations

from app.application.assistant.prompt_builder import (
    SYSTEM_INSTRUCTIONS,
    AssistantPromptBuilder,
)
from app.application.dtos.assistant import (
    AssistantContext,
    RetrievedItem,
)


def _item(object_id: str, title: str, sources=("search",), score=0.1) -> RetrievedItem:
    return RetrievedItem(
        object_id=object_id, object_type="document", title=title,
        version=1, sources=sources, score=score,
    )


def _context(history=(), retrieved=()) -> AssistantContext:
    return AssistantContext(
        question="q",
        history=tuple(history),
        retrieved=tuple(retrieved),
        truncated=False,
    )


def test_build_renders_all_sections_in_order():
    prompt = AssistantPromptBuilder().build(
        "find quantum",
        _context(
            history=(("user", "previous question"), ("assistant", "previous answer")),
            retrieved=(_item("obj:document:A", "Quantum Paper", ("search", "graph"), 0.5),),
        ),
    )
    user = prompt.user
    assert user.index("CONVERSATION HISTORY") < user.index("RETRIEVED CONTEXT") < user.index("QUESTION")
    assert "user: previous question" in user
    assert "assistant: previous answer" in user
    assert "[document] Quantum Paper" in user
    assert "obj:document:A" in user
    assert "source=search,graph" in user
    assert "score=0.5000" in user
    assert user.endswith("QUESTION:\nfind quantum")


def test_system_instructions_present():
    prompt = AssistantPromptBuilder().build("q", _context())
    assert prompt.system == SYSTEM_INSTRUCTIONS
    assert "UNTRUSTED DATA" in prompt.system  # injection-safety doctrine
    assert "permission-filtered" in prompt.system


def test_no_context_renders_question_only():
    prompt = AssistantPromptBuilder().build("hello", None)
    assert prompt.user == "QUESTION:\nhello"
    assert "RETRIEVED" not in prompt.user


def test_deterministic_across_builds():
    builder = AssistantPromptBuilder()
    context = _context(
        history=(("user", "h1"),),
        retrieved=(_item("obj:document:A", "Paper"),),
    )
    first = builder.build("find quantum", context)
    second = builder.build("find quantum", context)
    assert first == second


def test_deterministic_regardless_of_section_whitespace():
    """The renderer normalizes content placement — same data, same prompt."""
    builder = AssistantPromptBuilder()
    a = builder.build("  find quantum  ", _context(history=(("user", "hi"),)))
    b = builder.build("find quantum", _context(history=(("user", "hi"),)))
    assert "QUESTION:\nfind quantum" in a.user
    assert a.user == b.user


def test_cap_drops_retrieval_tail_never_the_question():
    builder = AssistantPromptBuilder()
    many = tuple(
        _item(f"obj:document:{i:03d}", f"Document {i}") for i in range(150)
    )
    prompt = builder.build("find quantum", _context(retrieved=many))
    assert len(prompt.user) <= 12000
    assert prompt.user.endswith("QUESTION:\nfind quantum")
    # The lowest-ranked (last) items were dropped first; the top ones remain.
    assert "Document 0" in prompt.user
    assert "Document 149" not in prompt.user


def test_cap_keeps_question_and_retrieval_head_drops_history_first():
    builder = AssistantPromptBuilder()
    huge_retrieval = tuple(
        _item(f"obj:document:{i:04d}", "X" * 300) for i in range(80)
    )
    prompt = builder.build("find quantum", _context(
        history=(("user", "earlier question"),), retrieved=huge_retrieval,
    ))
    # History is the OLDEST content: dropped first. The retrieval HEAD
    # (top-ranked items) survives within budget; the question always does.
    assert "earlier question" not in prompt.user
    assert "obj:document:0000" in prompt.user
    assert "obj:document:0079" not in prompt.user
    assert prompt.user.endswith("QUESTION:\nfind quantum")
    assert len(prompt.user) <= 12000
