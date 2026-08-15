"""Unit tests: ChatUseCase (Sprint M15 — F17 AI Chat over All Documents).

Proves the conversational contract: client-supplied history reaches the
generation prompt (coherent multi-turn), the latest message is still grounded
in authoritative document text, streaming is leak-proof, failures degrade
honestly, provenance is real, and history is capped. ChatUseCase composes the
existing GroundedQAUseCase, so these also confirm the (additive) conversation
generalisation did not change single-turn behaviour.
"""
from __future__ import annotations

from app.application.assistant.citations import CitationBuilder
from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.dtos.ai import GenerationEvent, GenerationResult, TokenUsage
from app.application.dtos.assistant import AssistantRetrievalResult, RetrievedItem
from app.application.use_cases.ai.chat import (
    _MAX_HISTORY_TURNS,
    CHAT_SYSTEM_INSTRUCTIONS,
    ChatTurn,
    ChatUseCase,
)
from app.application.use_cases.ai.grounded_qa import GroundedQAUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId

# --------------------------------------------------------------------------- mocks


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


class _FakeGateway:
    provider_id = "test-provider"

    def __init__(self, *, generate_text="Sure — based on the documents…", events=None, raise_in_stream_at=None):
        self._generate_text = generate_text
        self._events = list(events or [])
        self._raise_at = raise_in_stream_at
        self.last_prompt = None

    def generate(self, prompt):
        self.last_prompt = prompt
        return GenerationResult(
            text=self._generate_text, model="test-model",
            usage=TokenUsage(input_tokens=9, output_tokens=11, estimated=True), latency_ms=55,
        )

    def stream(self, prompt):
        self.last_prompt = prompt
        for index, event in enumerate(self._events):
            yield event
            if self._raise_at is not None and index == self._raise_at:
                raise RuntimeError("gateway stream failed")


class _MockAiCore:
    def __init__(self, gateway):
        self._gateway = gateway
        self.config = None

    def gateway(self):
        return self._gateway


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
    )


def _make(gateway, *, texts=None):
    annotation = _MockAnnotationService(texts or {})
    grounded = GroundedQAUseCase(
        repository=None,
        retrieval=_MockRetrieval(_items()),
        ai_core=_MockAiCore(gateway),
        context_builder=AssistantContextBuilder(),
        prompt_builder=AssistantPromptBuilder(system_instructions=CHAT_SYSTEM_INSTRUCTIONS),
        citation_builder=CitationBuilder(),
        verifier=None,
        annotation_service=annotation,
        storage=_MockStorage(),
    )
    return ChatUseCase(grounded)


# ===========================================================================
# history + grounding
# ===========================================================================


class TestHistoryAndGrounding:
    def test_history_reaches_prompt(self):
        gw = _FakeGateway()
        use_case = _make(gw, texts={"obj:document:d1": "Solar cells convert light."})
        history = [
            ChatTurn("user", "What is renewable energy?"),
            ChatTurn("assistant", "It comes from natural sources."),
        ]
        result = use_case.execute("Tell me more about solar", history, _user())
        prompt = gw.last_prompt.user
        # The prior turns are part of the conversation context.
        assert "What is renewable energy?" in prompt
        assert "It comes from natural sources." in prompt
        assert "Tell me more about solar" in prompt
        # The latest message is still grounded in document content.
        assert "Solar cells convert light." in prompt
        assert result.available is True

    def test_chat_system_instructions_used(self):
        gw = _FakeGateway()
        use_case = _make(gw, texts={"obj:document:d1": "x"})
        use_case.execute("hi", [], _user())
        assert "document chat assistant" in gw.last_prompt.system.lower()

    def test_no_history_still_grounded(self):
        gw = _FakeGateway()
        use_case = _make(gw, texts={"obj:document:d1": "Quantum entanglement."})
        result = use_case.execute("What is entanglement?", None, _user())
        assert result.available is True
        assert "Quantum entanglement." in gw.last_prompt.user


class TestHistoryCap:
    def test_only_newest_history_turns_kept(self):
        gw = _FakeGateway()
        use_case = _make(gw, texts={"obj:document:d1": "x"})
        # More turns than the cap; the OLDEST must be dropped.
        history = [ChatTurn("user", f"old-turn-{i}") for i in range(_MAX_HISTORY_TURNS + 5)]
        history.append(ChatTurn("user", "newest-turn"))
        use_case.execute("message", history, _user())
        prompt = gw.last_prompt.user
        assert "newest-turn" in prompt
        assert "old-turn-0" not in prompt  # oldest dropped


# ===========================================================================
# streaming (Phase B: provisional tokens + authoritative completion)
# ===========================================================================


class TestStreaming:
    def _events_ok(self):
        return [
            GenerationEvent(kind="token", delta="Hel"),
            GenerationEvent(kind="token", delta="lo"),
            GenerationEvent(kind="complete", result=GenerationResult(
                text="Hello", model="test-model", usage=TokenUsage(estimated=True))),
        ]

    def test_success_flushes_tokens_then_completion(self):
        gw = _FakeGateway(events=self._events_ok())
        use_case = _make(gw, texts={"obj:document:d1": "x"})
        events = list(use_case.stream("hi", [], _user()))
        tokens = [e["delta"] for e in events if e["type"] == "token"]
        completions = [e for e in events if e["type"] == "complete"]
        assert tokens == ["Hel", "lo"]
        assert len(completions) == 1 and completions[0]["result"].available is True

    def test_failure_marks_partial_preview_failed(self):
        # Phase B: provisional tokens may be previewed; the authoritative
        # completion still reports available=False (never a fake success).
        gw = _FakeGateway(events=[
            GenerationEvent(kind="token", delta="partial-"),
            GenerationEvent(kind="token", delta="leak"),
        ], raise_in_stream_at=1)
        use_case = _make(gw, texts={"obj:document:d1": "x"})
        events = list(use_case.stream("hi", [], _user()))
        assert [e["delta"] for e in events if e["type"] == "token"] == [
            "partial-", "leak",
        ]
        assert events[-1]["result"].available is False

    def test_incomplete_stream_is_failure(self):
        gw = _FakeGateway(events=[
            GenerationEvent(kind="token", delta="partial"),
        ])  # no complete event
        use_case = _make(gw, texts={"obj:document:d1": "x"})
        events = list(use_case.stream("hi", [], _user()))
        assert [e["delta"] for e in events if e["type"] == "token"] == [
            "partial",
        ]
        assert events[-1]["result"].available is False


# ===========================================================================
# fallback + provenance
# ===========================================================================


class TestFallbackAndProvenance:
    def test_gateway_failure_returns_honest_fallback(self):
        raising_gw = _FakeGateway()
        raising_gw.generate = lambda prompt: (_ for _ in ()).throw(RuntimeError("down"))
        use_case = _make(raising_gw, texts={"obj:document:d1": "x"})
        result = use_case.execute("hi", [ChatTurn("user", "previous")], _user())
        assert result.available is False

    def test_success_provenance_is_real(self):
        gw = _FakeGateway()
        use_case = _make(gw, texts={"obj:document:d1": "x"})
        result = use_case.execute("hi", [], _user())
        assert result.provider_id == "test-provider"
        assert result.model == "test-model"
        assert result.prompt_id == "assistant.default"
        assert result.input_tokens == 9 and result.output_tokens == 11
        assert result.latency_ms == 55
