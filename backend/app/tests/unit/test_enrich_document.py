"""Unit tests: EnrichDocumentUseCase (Sprint M13.2 / M13.2.1).

M13.2.1 — structured-output contract hardening (corrective). The enrichment
contract is now STRICTLY validated (pydantic strict mode, ``extra="forbid"``);
invalid provider output is REJECTED (``available=False``), never normalized.

Covers the audit's 21-point regression matrix (#1-#19 at the use-case level;
#20-#21 — master switch / flag gates — are in test_ai_enrich_api.py).
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
    """Records the structured prompt; returns a fixed structured value, or
    raises (to simulate a gateway-level failure such as invalid JSON)."""

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

    def generate(self, prompt):  # enrichment must NOT use generate()
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


def _enrich(gateway, text="Long paper text."):
    """Run enrichment with a readable document; return the EnrichmentResult."""
    return _use_case(gateway, extraction={"text": text}).execute(
        "obj:document:doc1", _user(), storage=None
    )


def _assert_rejected(result):
    """An invalid-output result must be the honest fallback, never success."""
    assert result.available is False
    assert result.title == ""
    assert result.summary == ""
    assert tuple(result.tags) == ()
    assert tuple(result.categories) == ()
    assert tuple(result.keywords) == ()


_GOOD_VALUE = {
    "title": "On Quantum Entanglement",
    "summary": "A study of entangled particles.",
    "tags": ["physics", "quantum"],
    "categories": ["research"],
    "keywords": ["entanglement", "particles"],
}


# --------------------------------------------------------------------------- permission & text


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
        with pytest.raises(ValidationError, match="No extracted text"):
            _use_case(gw, extraction=None).execute(
                "obj:document:doc1", _user(), storage=None
            )

    def test_empty_text_raises_validation(self):
        gw = _MockGateway(_GOOD_VALUE)
        with pytest.raises(ValidationError, match="No extracted text"):
            _use_case(gw, extraction={"text": ""}).execute(
                "obj:document:doc1", _user(), storage=None
            )


# --------------------------------------------------------------------------- success


class TestSuccessfulEnrichment:
    def test_valid_enrichment_passes(self):  # audit #1
        result = _enrich(_MockGateway(_GOOD_VALUE))
        assert result.available is True
        assert result.title == "On Quantum Entanglement"
        assert result.summary == "A study of entangled particles."
        assert tuple(result.tags) == ("physics", "quantum")
        assert tuple(result.categories) == ("research",)
        assert tuple(result.keywords) == ("entanglement", "particles")

    def test_uses_structured_generate_not_generate(self):
        gw = _MockGateway(_GOOD_VALUE)
        _enrich(gw)
        assert gw.structured_called is True
        assert gw.generate_called is False
        # The prompt carries the JSON schema (structured-generation contract).
        assert gw.last_prompt.schema["type"] == "object"
        assert "title" in gw.last_prompt.schema["properties"]

    def test_schema_is_strict_no_additional_properties(self):
        """The schema asserted to the model forbids extra fields (single
        source of truth with the validator)."""
        gw = _MockGateway(_GOOD_VALUE)
        _enrich(gw)
        assert gw.last_prompt.schema.get("additionalProperties") is False

    def test_untrusted_content_delimiters_in_prompt(self):
        gw = _MockGateway(_GOOD_VALUE)
        _enrich(gw, text="Secret doc.")
        assert "<<<DOCUMENT>>>" in gw.last_prompt.user
        assert "<<<END>>>" in gw.last_prompt.user
        assert "DATA" in gw.last_prompt.system or "data" in gw.last_prompt.system


# --------------------------------------------------------------------------- strict validation (audit #2-#14)


def _drop(key):
    return {k: v for k, v in _GOOD_VALUE.items() if k != key}


# Each case is one audit point; all must be REJECTED (available=False), not
# normalized into apparently-valid enrichment.
_REJECTION_CASES = [
    ("missing_title", _drop("title")),                                # #2
    ("missing_summary", _drop("summary")),                            # #3
    ("missing_tags", _drop("tags")),                                  # #4
    ("missing_categories", _drop("categories")),                      # #5
    ("missing_keywords", _drop("keywords")),                          # #6
    ("title_none", {**_GOOD_VALUE, "title": None}),                   # #7
    ("summary_none", {**_GOOD_VALUE, "summary": None}),               # #8
    ("tags_scalar", {**_GOOD_VALUE, "tags": "physics"}),              # #9
    ("categories_int", {**_GOOD_VALUE, "categories": 42}),            # #10
    ("keywords_non_string_item", {**_GOOD_VALUE, "keywords": ["ok", 7]}),  # #11
    ("extra_field", {**_GOOD_VALUE, "unexpected": "x"}),              # #12
    ("arbitrary_object", {"foo": "bar", "answer": 42}),               # #14
    ("empty_object", {}),                                             # arbitrary
    ("title_int_coercion", {**_GOOD_VALUE, "title": 123}),            # no 123->"123"
    ("tags_with_null", {**_GOOD_VALUE, "tags": ["a", None]}),         # null item
]


class TestStrictValidationRejectsInvalidOutput:
    @pytest.mark.parametrize("name,value", _REJECTION_CASES, ids=[c[0] for c in _REJECTION_CASES])
    def test_invalid_output_is_rejected(self, name, value):
        result = _enrich(_MockGateway(value))
        _assert_rejected(result)  # audit #2-#12, #14 (+ hardening extras)

    def test_invalid_json_is_rejected(self):  # audit #13
        # The real gateway raises on invalid JSON (covered by
        # test_openai_adapter_hardening); the use case converts any gateway
        # error into the honest fallback.
        result = _enrich(_MockGateway(raise_exc=RuntimeError("not valid JSON")))
        _assert_rejected(result)


# --------------------------------------------------------------------------- invalid-output contract (audit #15-#16)


class TestInvalidOutputContract:
    def test_invalid_output_returns_available_false(self):  # audit #15
        result = _enrich(_MockGateway({"only": "this"}))
        assert result.available is False

    def test_invalid_output_does_not_reach_success_path(self):  # audit #16
        """A schema-violating value must never populate the result fields —
        even fields that happened to be valid in the bad payload stay empty."""
        result = _enrich(_MockGateway({
            "title": "Looks Fine",       # valid on its own...
            "summary": "",               # ...but tags/categories/keywords missing
        }))
        assert result.available is False
        assert result.title == ""  # NOT "Looks Fine" — success path was not taken


# --------------------------------------------------------------------------- fallback & provenance


class TestGatewayFallback:
    def test_provider_failure_returns_honest_fallback(self):  # audit #17
        result = _enrich(_MockGateway(raise_exc=RuntimeError("provider down")))
        _assert_rejected(result)
        assert result.chars_total == len("Long paper text.")


class TestProvenance:
    def test_valid_provenance_preserved(self):  # audit #18
        result = _enrich(_MockGateway(_GOOD_VALUE))
        assert result.provider_id == "test-provider"
        assert result.model == "test-model"
        assert result.prompt_id == "ai.enrich"
        assert result.prompt_version == 1
        assert result.input_tokens == 11
        assert result.output_tokens == 23
        assert result.latency_ms == 88

    def test_fallback_provenance_internally_consistent(self):  # audit #19
        """Fallback claims no provider/model (none produced output) but still
        records the prompt identity — self-consistent, never fabricated."""
        result = _enrich(_MockGateway(raise_exc=RuntimeError("down")))
        assert result.available is False
        assert result.provider_id == ""   # honest: no provider produced output
        assert result.model == ""         # honest: no model produced output
        assert result.prompt_id == "ai.enrich"
        assert result.prompt_version == 1


# --------------------------------------------------------------------------- truncation


class TestTruncation:
    def test_long_text_truncated_with_disclosure(self):
        long_text = "x" * 20000  # exceeds _MAX_DOC_CHARS (12000)
        result = _enrich(_MockGateway(_GOOD_VALUE), text=long_text)
        assert result.truncated is True
        assert result.chars_total == 20000
        assert result.chars_used == 12000

    def test_short_text_not_truncated(self):
        result = _enrich(_MockGateway(_GOOD_VALUE), text="Short.")
        assert result.truncated is False
        assert result.chars_used == result.chars_total == len("Short.")
