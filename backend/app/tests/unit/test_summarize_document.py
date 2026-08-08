"""Unit tests: SummarizeDocumentUseCase (Sprint M12.1).

Behaviour-focused: permission enforcement, extracted-text requirement,
truncation disclosure, untrusted-content delimiters, honest gateway fallback.
All dependencies mocked — no network, no database.
"""
from __future__ import annotations

import pytest

from app.application.dtos.ai import GenerationResult, TokenUsage
from app.application.exceptions import (
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.application.use_cases.ai.summarize_document import (
    SummarizeDocumentUseCase,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId

# --------------------------------------------------------------------------- mocks


class _MockRepo:
    def __init__(self, doc=None):
        self._doc = doc

    def get_by_id(self, oid):
        return self._doc


class _MockAnnotationService:
    def __init__(self, extraction=None):
        self._extraction = extraction

    def extracted_text(self, document_id, storage):
        return self._extraction


class _MockEvaluator:
    def __init__(self, allow=True):
        self._allow = allow

    def can(self, **kwargs):
        return self._allow


class _MockGateway:
    provider_id = "test-provider"

    def __init__(self, text="A concise summary.", raise_exc=None, result=None):
        self._text = text
        self._raise = raise_exc
        self._result = result
        self.last_prompt = None

    def generate(self, prompt):
        self.last_prompt = prompt
        if self._raise:
            raise self._raise
        if self._result is not None:
            return self._result
        return GenerationResult(
            text=self._text, model="test-model", usage=TokenUsage(estimated=True)
        )


class _MockAiCore:
    def __init__(self, gateway):
        self._gateway = gateway
        self.config = type("Cfg", (), {"max_tokens": 2048})()

    def gateway(self):
        return self._gateway


def _user():
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:alice-0001"),
    )


def _doc(doc_id="obj:document:doc1"):
    return UniversalObject.create(
        ObjectType.DOCUMENT, "Paper", created_by="system",
        object_id=ObjectId(doc_id),
    )


# --------------------------------------------------------------------------- tests


class TestPermission:
    def test_permission_denied_raises(self):
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService({"text": "hello"}),
            _MockEvaluator(allow=False), _MockAiCore(_MockGateway()),
        )
        with pytest.raises(PermissionDeniedError, match="READ"):
            use_case.execute("obj:document:doc1", _user(), storage=None)

    def test_document_not_found_raises(self):
        use_case = SummarizeDocumentUseCase(
            _MockRepo(None), _MockAnnotationService(),
            _MockEvaluator(allow=True), _MockAiCore(_MockGateway()),
        )
        with pytest.raises(ObjectNotFoundError):
            use_case.execute("obj:document:ghost", _user(), storage=None)


class TestExtractedText:
    def test_no_extraction_raises_validation(self):
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService(extraction=None),
            _MockEvaluator(allow=True), _MockAiCore(_MockGateway()),
        )
        with pytest.raises(ValidationError, match="No extracted text"):
            use_case.execute("obj:document:doc1", _user(), storage=None)

    def test_empty_text_raises_validation(self):
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService(extraction={"text": ""}),
            _MockEvaluator(allow=True), _MockAiCore(_MockGateway()),
        )
        with pytest.raises(ValidationError, match="No extracted text"):
            use_case.execute("obj:document:doc1", _user(), storage=None)


class TestSuccessfulSummary:
    def test_returns_summary(self):
        gw = _MockGateway(text="This paper discusses quantum mechanics.")
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService({"text": "Long paper text."}),
            _MockEvaluator(allow=True), _MockAiCore(gw),
        )
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.available is True
        assert result.summary == "This paper discusses quantum mechanics."
        assert result.chars_total == len("Long paper text.")

    def test_untrusted_content_delimiters_in_prompt(self):
        gw = _MockGateway()
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService({"text": "Secret doc."}),
            _MockEvaluator(allow=True), _MockAiCore(gw),
        )
        use_case.execute("obj:document:doc1", _user(), storage=None)
        assert "<<<DOCUMENT>>>" in gw.last_prompt.user
        assert "<<<END>>>" in gw.last_prompt.user
        assert "DATA" in gw.last_prompt.system or "data" in gw.last_prompt.system


class TestTruncation:
    def test_long_text_truncated_with_disclosure(self):
        long_text = "x" * 20000  # exceeds _MAX_DOC_CHARS (12000)
        gw = _MockGateway()
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService({"text": long_text}),
            _MockEvaluator(allow=True), _MockAiCore(gw),
        )
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.truncated is True
        assert result.chars_total == 20000
        assert result.chars_used == 12000

    def test_short_text_not_truncated(self):
        gw = _MockGateway()
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService({"text": "Short."}),
            _MockEvaluator(allow=True), _MockAiCore(gw),
        )
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.truncated is False
        assert result.chars_used == result.chars_total == len("Short.")


class TestGatewayFallback:
    def test_gateway_failure_returns_honest_fallback(self):
        gw = _MockGateway(raise_exc=RuntimeError("provider down"))
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService({"text": "Some text."}),
            _MockEvaluator(allow=True), _MockAiCore(gw),
        )
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.available is False
        assert "unavailable" in result.summary.lower()
        assert result.chars_total == len("Some text.")


class TestProvenance:
    """M13.3 — provenance contract retrofitted into summarization."""

    def test_success_provenance_from_generation_result(self):
        gw = _MockGateway(result=GenerationResult(
            text="A summary.", model="gpt-4o-mini",
            usage=TokenUsage(input_tokens=5, output_tokens=7, estimated=False),
            latency_ms=42,
        ))
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService({"text": "doc text"}),
            _MockEvaluator(allow=True), _MockAiCore(gw),
        )
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.available is True
        assert result.provider_id == "test-provider"
        assert result.model == "gpt-4o-mini"
        assert result.prompt_id == "ai.summarize"
        assert result.prompt_version == 1
        assert result.input_tokens == 5
        assert result.output_tokens == 7
        assert result.token_usage_estimated is False
        assert result.latency_ms == 42

    def test_estimated_usage_when_provider_reports_none(self):
        gw = _MockGateway()  # default TokenUsage(estimated=True), 0 tokens
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService({"text": "doc text"}),
            _MockEvaluator(allow=True), _MockAiCore(gw),
        )
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.token_usage_estimated is True
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_fallback_provenance_internally_consistent(self):
        gw = _MockGateway(raise_exc=RuntimeError("down"))
        use_case = SummarizeDocumentUseCase(
            _MockRepo(_doc()), _MockAnnotationService({"text": "doc text"}),
            _MockEvaluator(allow=True), _MockAiCore(gw),
        )
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.available is False
        # Honest: no provider/model produced output.
        assert result.provider_id == ""
        assert result.model == ""
        # But the prompt identity is still recorded (self-consistent).
        assert result.prompt_id == "ai.summarize"
        assert result.prompt_version == 1
        assert result.input_tokens == 0
        assert result.latency_ms == 0
