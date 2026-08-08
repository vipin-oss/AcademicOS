"""Unit tests: GroundedQAUseCase (Sprint M13.1.1 — corrective sprint).

Regression coverage for the three production-critical defects:

- **Defect 1 — streaming leak**: partial answers never reach the client.
  Tokens are buffered and flushed only after a confirmed completion; a
  stream that fails or ends without a completion is a generation failure.
- **Defect 2 — grounding**: the authoritative source text actually reaches
  the generation prompt (reusing the intake-extraction pipeline), not just
  document titles.
- **Defect 3 — provenance**: ``prompt_id`` / ``prompt_version`` are the
  values produced by the prompt builder (``assistant.default``), never a
  hardcoded identity.

All dependencies are mocked — no network, no database, no real gateway.
"""
from __future__ import annotations

from app.application.assistant.citations import CitationBuilder
from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.dtos.ai import (
    GenerationEvent,
    GenerationResult,
    TokenUsage,
)
from app.application.dtos.assistant import (
    AssistantRetrievalResult,
    RetrievedItem,
)
from app.application.use_cases.ai.grounded_qa import (
    _FALLBACK_ANSWER,
    _MAX_SOURCE_CHARS_PER_ITEM,
    GroundedQAUseCase,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId

# --------------------------------------------------------------------------- mocks


class _MockRetrieval:
    """Permission-filtered retrieval stub returning a fixed result set."""

    def __init__(self, items):
        self._items = items

    def retrieve(self, query, user, **kwargs):
        return AssistantRetrievalResult(
            items=tuple(self._items),
            search_count=len(self._items),
            graph_count=0,
        )


class _MockAnnotationService:
    """Stand-in for DocumentAnnotationService (the intake text pipeline)."""

    def __init__(self, texts):
        self._texts = texts  # object_id -> text
        self.calls = []

    def extracted_text(self, document_id, storage):
        self.calls.append(document_id)
        text = self._texts.get(document_id)
        if not text:
            return None
        return {"text": text}


class _MockStorage:
    """FileStorage stub (the annotation-service mock does not touch it)."""


class _FakeGateway:
    """Configurable gateway: records the prompt, returns a fixed generate
    result, and streams a scripted event sequence (optionally raising
    mid-stream)."""

    provider_id = "test-provider"

    def __init__(self, *, generate_text="final answer", events=None, raise_in_stream_at=None):
        self._generate_text = generate_text
        self._events = list(events or [])
        self._raise_at = raise_in_stream_at
        self.last_prompt = None

    def generate(self, prompt):
        self.last_prompt = prompt
        return GenerationResult(
            text=self._generate_text,
            model="test-model",
            usage=TokenUsage(input_tokens=5, output_tokens=7, estimated=True),
            latency_ms=42,
        )

    def stream(self, prompt):
        self.last_prompt = prompt
        for index, event in enumerate(self._events):
            yield event
            if self._raise_at is not None and index == self._raise_at:
                raise RuntimeError("gateway stream failed mid-flight")


class _MockAiCore:
    def __init__(self, gateway):
        self._gateway = gateway
        self.config = None

    def gateway(self):
        return self._gateway


# --------------------------------------------------------------------------- fixtures


def _user():
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:alice-0001"),
    )


def _items():
    return (
        RetrievedItem(
            object_id="obj:document:d1", object_type="document",
            title="Quantum Paper", version=1, sources=("search",), score=0.9,
        ),
        RetrievedItem(
            object_id="obj:document:d2", object_type="document",
            title="Neural Nets", version=1, sources=("search",), score=0.8,
        ),
    )


def _make_use_case(gateway, *, annotation_texts=None):
    """Build a use case with the REAL context/citation/prompt builders so the
    composition (grounding + provenance) is exercised, but mocked edges."""
    annotation = _MockAnnotationService(annotation_texts or {})
    return (
        GroundedQAUseCase(
            repository=None,
            retrieval=_MockRetrieval(_items()),
            ai_core=_MockAiCore(gateway),
            context_builder=AssistantContextBuilder(),
            prompt_builder=AssistantPromptBuilder(),
            citation_builder=CitationBuilder(),
            verifier=None,  # verifier covered by its own suite
            annotation_service=annotation,
            storage=_MockStorage(),
        ),
        annotation,
    )


# ===========================================================================
# DEFECT 1 — streaming leak
# ===========================================================================


class TestStreamingLeak:
    def _drain(self, use_case):
        return list(use_case.stream("any question", _user()))

    def test_successful_stream_emits_tokens_then_completion(self):
        gw = _FakeGateway(
            generate_text="full answer",
            events=[
                GenerationEvent(kind="token", delta="full "),
                GenerationEvent(kind="token", delta="answer"),
                GenerationEvent(
                    kind="complete",
                    result=GenerationResult(
                        text="full answer", model="test-model",
                        usage=TokenUsage(estimated=True),
                    ),
                ),
            ],
        )
        use_case, _ = _make_use_case(gw)
        events = self._drain(use_case)

        token_deltas = [e["delta"] for e in events if e["type"] == "token"]
        completions = [e for e in events if e["type"] == "complete"]
        assert token_deltas == ["full ", "answer"]
        assert len(completions) == 1
        result = completions[0]["result"]
        assert result.available is True
        assert result.answer == "full answer"

    def test_gateway_failure_mid_stream_leaks_no_tokens(self):
        """Tokens buffered before the failure must never be emitted."""
        gw = _FakeGateway(
            events=[
                GenerationEvent(kind="token", delta="partial-"),
                GenerationEvent(kind="token", delta="leak"),
            ],
            raise_in_stream_at=1,  # raise after the second token
        )
        use_case, _ = _make_use_case(gw)
        events = self._drain(use_case)

        assert not any(e["type"] == "token" for e in events), "tokens leaked"
        assert len(events) == 1
        result = events[0]["result"]
        assert result.available is False
        assert result.answer == _FALLBACK_ANSWER

    def test_stream_without_completion_event_is_generation_failure(self):
        """A stream that ends with no completion event is NOT a success."""
        gw = _FakeGateway(
            events=[
                GenerationEvent(kind="token", delta="partial-"),
                GenerationEvent(kind="token", delta="answer"),
            ],
            # no raise, no complete event — generator simply ends
        )
        use_case, _ = _make_use_case(gw)
        events = self._drain(use_case)

        assert not any(e["type"] == "token" for e in events), "tokens leaked"
        assert len(events) == 1
        result = events[0]["result"]
        assert result.available is False
        assert result.answer == _FALLBACK_ANSWER

    def test_streaming_fallback_matches_sync_honesty_contract(self):
        # Sync fallback: gateway.generate raises.
        raising_gw = _FakeGateway()
        raising_gw.generate = lambda prompt: (_ for _ in ()).throw(
            RuntimeError("down")
        )
        sync_result = _make_use_case(raising_gw)[0].execute("q", _user())

        # Streaming fallback: the stream raises after emitting a token.
        stream_gw = _FakeGateway(
            events=[GenerationEvent(kind="token", delta="x")],
            raise_in_stream_at=0,
        )
        stream_events = list(_make_use_case(stream_gw)[0].stream("q", _user()))
        stream_result = stream_events[-1]["result"]

        assert sync_result.available is False
        assert stream_result.available is False
        # Same honest message on both paths — identical honesty contract.
        assert sync_result.answer == stream_result.answer == _FALLBACK_ANSWER


# ===========================================================================
# DEFECT 2 — grounding (source text reaches the prompt)
# ===========================================================================


class TestGrounding:
    def test_authoritative_source_text_reaches_prompt(self):
        gw = _FakeGateway()
        texts = {
            "obj:document:d1": "Quantum entanglement links particles instantly.",
            "obj:document:d2": "Neural networks learn from labelled examples.",
        }
        use_case, annotation = _make_use_case(gw, annotation_texts=texts)
        use_case.execute("What is entanglement?", _user())

        prompt = gw.last_prompt.user
        # The actual document CONTENT (not just titles) reaches the model.
        assert "Quantum entanglement links particles instantly." in prompt
        assert "Neural networks learn from labelled examples." in prompt
        # Delimited as untrusted data.
        assert "<<<SOURCE TEXT>>>" in prompt
        assert "<<<END>>>" in prompt
        # The existing intake pipeline was reused (not a new retrieval).
        assert "obj:document:d1" in annotation.calls
        assert "obj:document:d2" in annotation.calls

    def test_each_passage_carries_its_citation_number(self):
        gw = _FakeGateway()
        use_case, _ = _make_use_case(
            gw,
            annotation_texts={"obj:document:d1": "PASSAGE-ONE"},
        )
        use_case.execute("q", _user())
        prompt = gw.last_prompt.user
        # Marker [1] precedes the passage so the model can cite it.
        assert "[1] Quantum Paper\n<<<SOURCE TEXT>>>\nPASSAGE-ONE" in prompt

    def test_missing_text_is_skipped_not_fatal(self):
        gw = _FakeGateway()
        use_case, _ = _make_use_case(
            gw, annotation_texts={"obj:document:d1": "ONLY-THIS-PASSAGE"},
        )
        use_case.execute("q", _user())
        prompt = gw.last_prompt.user
        assert "ONLY-THIS-PASSAGE" in prompt
        # d2 had no extracted text -> no empty passage block is injected.
        assert "Neural Nets\n<<<SOURCE TEXT>>>" not in prompt

    def test_long_source_text_truncated_and_disclosed(self):
        gw = _FakeGateway()
        long_text = "Z" * 5000  # exceeds _MAX_SOURCE_CHARS_PER_ITEM (2000)
        use_case, _ = _make_use_case(
            gw, annotation_texts={"obj:document:d1": long_text},
        )
        result = use_case.execute("q", _user())
        assert result.truncated is True
        # The injected passage is capped to the per-item budget.
        assert gw.last_prompt.user.count("Z") <= _MAX_SOURCE_CHARS_PER_ITEM
        assert gw.last_prompt.user.count("Z") > 0

    def test_no_annotation_service_keeps_backward_compatible_prompt(self):
        """Without the text source the prompt is the pre-fix envelope."""
        gw = _FakeGateway()
        use_case = GroundedQAUseCase(
            repository=None,
            retrieval=_MockRetrieval(_items()),
            ai_core=_MockAiCore(gw),
            context_builder=AssistantContextBuilder(),
            prompt_builder=AssistantPromptBuilder(),
            citation_builder=CitationBuilder(),
            verifier=None,
            # annotation_service + storage omitted
        )
        use_case.execute("q", _user())
        assert "<<<SOURCE TEXT>>>" not in gw.last_prompt.user
        # Retrieved titles still present.
        assert "Quantum Paper" in gw.last_prompt.user


# ===========================================================================
# DEFECT 3 — provenance reports the actual prompt identity
# ===========================================================================


class TestProvenance:
    def test_success_reports_builder_prompt_id_not_hardcoded(self):
        gw = _FakeGateway()
        use_case, _ = _make_use_case(gw)
        result = use_case.execute("q", _user())
        assert result.prompt_id == "assistant.default"
        assert result.prompt_version == 1
        assert result.prompt_id != "ai.grounded_qa"
        assert result.provider_id == "test-provider"
        assert result.model == "test-model"

    def test_sync_fallback_reports_consistent_provenance(self):
        raising_gw = _FakeGateway()
        raising_gw.generate = lambda prompt: (_ for _ in ()).throw(RuntimeError("down"))
        use_case, _ = _make_use_case(raising_gw)
        result = use_case.execute("q", _user())
        assert result.available is False
        assert result.prompt_id == "assistant.default"
        assert result.prompt_version == 1

    def test_streaming_success_reports_consistent_provenance(self):
        gw = _FakeGateway(
            events=[
                GenerationEvent(kind="token", delta="hi"),
                GenerationEvent(
                    kind="complete",
                    result=GenerationResult(
                        text="hi", model="test-model",
                        usage=TokenUsage(estimated=True),
                    ),
                ),
            ],
        )
        use_case, _ = _make_use_case(gw)
        events = list(use_case.stream("q", _user()))
        result = events[-1]["result"]
        assert result.available is True
        assert result.prompt_id == "assistant.default"
        assert result.prompt_version == 1

    def test_streaming_fallback_reports_consistent_provenance(self):
        gw = _FakeGateway(
            events=[GenerationEvent(kind="token", delta="x")],
            raise_in_stream_at=0,
        )
        use_case, _ = _make_use_case(gw)
        events = list(use_case.stream("q", _user()))
        result = events[-1]["result"]
        assert result.available is False
        assert result.prompt_id == "assistant.default"
        assert result.prompt_version == 1
