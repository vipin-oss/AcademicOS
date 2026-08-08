"""Unit tests: EnrichDocumentUseCase (Sprint M13.2).

Behaviour-focused: permission enforcement, extracted-text requirement,
truncation disclosure, untrusted-content delimiters, structured-response
validation, honest gateway fallback, and provenance. The first production
use of ``structured_generate``. All dependencies mocked — no network, no db.
"""
from __future__ import annotations

import json

import pytest

from app.application.dtos.ai import (
    StructuredGenerationResult,
    TokenUsage,
)
from app.application.exceptions import (
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.application.use_cases.ai.enrich_document import EnrichDocumentUseCase
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
    """Records the structured prompt; returns a fixed structured value."""

    provider_id = "test-provider"

    def __init__(self, value=None, raise_exc=None):
        self._value = value if value is not None else {}
        self._raise = raise_exc
        self.last_prompt = None
        self.structured_called = False
        self.generate_called = False

    def structured_generate(self, prompt):
        self.structured_called = True
        self.last_prompt = prompt
        if self._raise:
            raise self._raise
        return StructuredGenerationResult(
            value=self._value,
            raw_text=json.dumps(self._value),
            model="test-model",
            usage=TokenUsage(input_tokens=11, output_tokens=23, estimated=True),
            latency_ms=88,
        )

    def generate(self, prompt):  # must NOT be used by enrichment
        self.generate_called = True
        raise AssertionError("enrichment must use structured_generate, not generate")


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


def _use_case(gateway, *, allow=True, extraction=None, doc=None):
    return EnrichDocumentUseCase(
        _MockRepo(doc if doc is not None else _doc()),
        _MockAnnotationService(extraction),
        _MockEvaluator(allow=allow),
        _MockAiCore(gateway),
    )


_GOOD_VALUE = {
    "title": "On Quantum Entanglement",
    "summary": "A study of entangled particles.",
    "tags": ["physics", "quantum"],
    "categories": ["research"],
    "keywords": ["entanglement", "particles"],
}


# --------------------------------------------------------------------------- tests


class TestPermission:
    def test_permission_denied_raises(self):
        gw = _MockGateway(_GOOD_VALUE)
        use_case = _use_case(gw, allow=False, extraction={"text": "hello"})
        with pytest.raises(PermissionDeniedError, match="READ"):
            use_case.execute("obj:document:doc1", _user(), storage=None)
        assert not gw.structured_called  # never reached the gateway

    def test_document_not_found_raises(self):
        gw = _MockGateway(_GOOD_VALUE)
        use_case = EnrichDocumentUseCase(
            _MockRepo(None), _MockAnnotationService({"text": "x"}),
            _MockEvaluator(allow=True), _MockAiCore(gw),
        )
        with pytest.raises(ObjectNotFoundError):
            use_case.execute("obj:document:ghost", _user(), storage=None)


class TestExtractedText:
    def test_no_extraction_raises_validation(self):
        gw = _MockGateway(_GOOD_VALUE)
        use_case = _use_case(gw, extraction=None)
        with pytest.raises(ValidationError, match="No extracted text"):
            use_case.execute("obj:document:doc1", _user(), storage=None)

    def test_empty_text_raises_validation(self):
        gw = _MockGateway(_GOOD_VALUE)
        use_case = _use_case(gw, extraction={"text": ""})
        with pytest.raises(ValidationError, match="No extracted text"):
            use_case.execute("obj:document:doc1", _user(), storage=None)


class TestSuccessfulEnrichment:
    def test_returns_structured_fields(self):
        gw = _MockGateway(_GOOD_VALUE)
        use_case = _use_case(gw, extraction={"text": "Long paper text."})
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.available is True
        assert result.title == "On Quantum Entanglement"
        assert result.summary == "A study of entangled particles."
        assert tuple(result.tags) == ("physics", "quantum")
        assert tuple(result.categories) == ("research",)
        assert tuple(result.keywords) == ("entanglement", "particles")

    def test_uses_structured_generate_not_generate(self):
        gw = _MockGateway(_GOOD_VALUE)
        use_case = _use_case(gw, extraction={"text": "Some text."})
        use_case.execute("obj:document:doc1", _user(), storage=None)
        assert gw.structured_called is True
        assert gw.generate_called is False
        # The prompt carries the JSON schema (structured-generation contract).
        assert gw.last_prompt.schema["type"] == "object"
        assert "title" in gw.last_prompt.schema["properties"]

    def test_untrusted_content_delimiters_in_prompt(self):
        gw = _MockGateway(_GOOD_VALUE)
        use_case = _use_case(gw, extraction={"text": "Secret doc."})
        use_case.execute("obj:document:doc1", _user(), storage=None)
        assert "<<<DOCUMENT>>>" in gw.last_prompt.user
        assert "<<<END>>>" in gw.last_prompt.user
        assert "DATA" in gw.last_prompt.system or "data" in gw.last_prompt.system

    def test_provenance_present(self):
        gw = _MockGateway(_GOOD_VALUE)
        use_case = _use_case(gw, extraction={"text": "Text."})
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.provider_id == "test-provider"
        assert result.model == "test-model"
        assert result.prompt_id == "ai.enrich"
        assert result.prompt_version == 1
        assert result.input_tokens == 11
        assert result.output_tokens == 23
        assert result.latency_ms == 88


class TestStructuredValidation:
    """The model's JSON is coerced + validated; bad shapes degrade gracefully."""

    def test_missing_keys_default_to_empty(self):
        gw = _MockGateway({"title": "Only Title"})
        use_case = _use_case(gw, extraction={"text": "x"})
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.available is True
        assert result.title == "Only Title"
        assert result.summary == ""
        assert tuple(result.tags) == ()
        assert tuple(result.categories) == ()
        assert tuple(result.keywords) == ()

    def test_wrong_types_coerced(self):
        gw = _MockGateway({
            "title": 123,           # non-string -> stringified
            "summary": None,        # -> empty
            "tags": "physics",      # not a list -> empty
            "categories": 42,       # not a list -> empty
            "keywords": ["a", 7, "b"],  # list with non-strings -> coerced to str
        })
        use_case = _use_case(gw, extraction={"text": "x"})
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.title == "123"
        assert result.summary == ""
        assert tuple(result.tags) == ()
        assert tuple(result.categories) == ()
        assert tuple(result.keywords) == ("a", "7", "b")

    def test_extra_keys_ignored(self):
        gw = _MockGateway({**_GOOD_VALUE, "malicious": "ignored", "foo": ["bar"]})
        use_case = _use_case(gw, extraction={"text": "x"})
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert tuple(result.tags) == ("physics", "quantum")
        assert result.available is True


class TestTruncation:
    def test_long_text_truncated_with_disclosure(self):
        long_text = "x" * 20000  # exceeds _MAX_DOC_CHARS (12000)
        gw = _MockGateway(_GOOD_VALUE)
        use_case = _use_case(gw, extraction={"text": long_text})
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.truncated is True
        assert result.chars_total == 20000
        assert result.chars_used == 12000

    def test_short_text_not_truncated(self):
        gw = _MockGateway(_GOOD_VALUE)
        use_case = _use_case(gw, extraction={"text": "Short."})
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.truncated is False
        assert result.chars_used == result.chars_total == len("Short.")


class TestGatewayFallback:
    def test_gateway_failure_returns_honest_fallback(self):
        gw = _MockGateway(raise_exc=RuntimeError("provider down"))
        use_case = _use_case(gw, extraction={"text": "Some text."})
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.available is False
        assert result.title == ""
        assert result.summary == ""
        assert tuple(result.tags) == ()
        assert result.chars_total == len("Some text.")
        # Provenance identity still recorded (no provider/model on fallback).
        assert result.prompt_id == "ai.enrich"

    def test_malformed_structured_response_is_handled(self):
        """structured_generate itself parses JSON; but a gateway that returns
        a non-object value dict is coerced, not crashed."""
        gw = _MockGateway({})  # empty object — all fields default
        use_case = _use_case(gw, extraction={"text": "x"})
        result = use_case.execute("obj:document:doc1", _user(), storage=None)
        assert result.available is True
        assert result.title == ""  # coerced, not crashed

