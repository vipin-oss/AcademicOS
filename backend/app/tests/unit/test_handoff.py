"""Unit tests: HandoffUseCase (Sprint M16 — external-AI handoff).

Proves the no-provider / no-cost path: the grounded prompt (with authoritative
source text) is built and handed back as a copyable bundle, NO gateway is
invoked, only READ-permission-filtered sources appear, and bad input is
rejected.
"""
from __future__ import annotations

import pytest

from app.application.assistant.citations import CitationBuilder
from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.dtos.assistant import AssistantRetrievalResult, RetrievedItem
from app.application.use_cases.ai.grounded_qa import GroundedQAUseCase
from app.application.use_cases.ai.handoff import HandoffUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId


class _MockRetrieval:
    def __init__(self, items):
        self._items = items

    def retrieve(self, query, user, **kwargs):
        return AssistantRetrievalResult(
            items=tuple(self._items), search_count=len(self._items), graph_count=0,
        )


class _MockAnnotationService:
    def __init__(self, texts):
        self._texts = texts

    def extracted_text(self, document_id, storage):
        text = self._texts.get(document_id)
        return {"text": text} if text else None


class _MockStorage:
    pass


class _NoGatewayCore:
    """An AI Core whose gateway() raises if called — the handoff must never call it."""

    config = None

    def gateway(self):
        raise AssertionError("handoff must not invoke the gateway (no-cost path)")


def _user():
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:alice-0001"),
    )


def _items():
    return (
        RetrievedItem(
            object_id="obj:document:d1", object_type="document",
            title="Energy Paper", version=1, sources=("search",), score=0.9,
        ),
        RetrievedItem(
            object_id="obj:document:d2", object_type="document",
            title="Solar Notes", version=1, sources=("search",), score=0.8,
        ),
    )


def _make(texts=None):
    grounded = GroundedQAUseCase(
        repository=None,
        retrieval=_MockRetrieval(_items()),
        ai_core=_NoGatewayCore(),
        context_builder=AssistantContextBuilder(),
        prompt_builder=AssistantPromptBuilder(),
        citation_builder=CitationBuilder(),
        verifier=None,
        annotation_service=_MockAnnotationService(texts or {}),
        storage=_MockStorage(),
    )
    return HandoffUseCase(grounded)


class TestHandoffBundle:
    def test_builds_grounded_bundle_without_gateway(self):
        use_case = _make({"obj:document:d1": "Solar power is renewable."})
        bundle = use_case.execute("qa", "What is solar energy?", _user())
        # No gateway was invoked (would have raised) -> we got here.
        assert bundle.task == "qa"
        assert bundle.system_prompt
        assert bundle.user_prompt
        assert bundle.combined_prompt == f"{bundle.system_prompt}\n\n---\n\n{bundle.user_prompt}"

    def test_source_content_is_in_the_prompt(self):
        use_case = _make({"obj:document:d1": "Solar power is renewable."})
        bundle = use_case.execute("qa", "solar?", _user())
        assert "Solar power is renewable." in bundle.user_prompt

    def test_readable_sources_listed(self):
        use_case = _make({"obj:document:d1": "x", "obj:document:d2": "y"})
        bundle = use_case.execute("qa", "q", _user())
        titles = {s.title for s in bundle.sources}
        assert titles == {"Energy Paper", "Solar Notes"}
        assert bundle.source_count == 2
        assert all(s.number >= 1 for s in bundle.sources)

    def test_note_explains_no_cost_external_use(self):
        bundle = _make({"obj:document:d1": "x"}).execute("qa", "q", _user())
        note_l = bundle.note.lower()
        assert "no cost" in note_l or "no charge" in note_l
        assert "copy" in note_l  # actionable: copy into an external AI

    def test_expected_format_and_instructions_present(self):
        bundle = _make({"obj:document:d1": "x"}).execute("qa", "q", _user())
        assert bundle.expected_format
        assert bundle.instructions


class TestValidation:
    def test_unsupported_task_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            _make({"obj:document:d1": "x"}).execute("summarize", "q", _user())

    def test_empty_question_raises(self):
        with pytest.raises(ValueError, match="non-empty question"):
            _make({"obj:document:d1": "x"}).execute("qa", "   ", _user())


class TestNoSourceText:
    def test_bundle_still_built_when_no_extracted_text(self):
        # No annotation text -> prompt has no SOURCE CONTENT section, but the
        # bundle (metadata-only context) is still returned honestly.
        use_case = _make(texts={})
        bundle = use_case.execute("qa", "q", _user())
        assert bundle.task == "qa"
        assert "<<<SOURCE TEXT>>>" not in bundle.user_prompt
