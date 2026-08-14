"""Capability evaluation case shape (L0).

There is no ``intent`` field. Phrasings are evaluation data, not routes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


ALLOWED_LANGUAGES = frozenset({"en", "hi-en"})
ALLOWED_GATE_LEVELS = frozenset({"l0_data", "l4", "l5", "l7", "l9"})
FORBIDDEN_CASE_KEYS = frozenset(
    {"intent", "INTENT_", "expected_intent", "intent_code", "parsed_intent"}
)


@dataclass(frozen=True)
class CapabilityCheck:
    """Capability-level predicates. L0 validates shape; later levels hard-gate."""

    output_kind: str | None = None
    evidence_required: bool | None = None
    named_document_required: bool | None = None
    refusal_expected: bool | None = None
    clarify_expected: bool | None = None
    count_equals: int | None = None
    retrieval_must_include_types: tuple[str, ...] = ()
    no_leak: bool | None = None
    must_not_require_named_document: bool | None = None

    @classmethod
    def from_mapping(cls, data: dict) -> CapabilityCheck:
        types = data.get("retrieval_must_include_types") or ()
        return cls(
            output_kind=data.get("output_kind"),
            evidence_required=data.get("evidence_required"),
            named_document_required=data.get("named_document_required"),
            refusal_expected=data.get("refusal_expected"),
            clarify_expected=data.get("clarify_expected"),
            count_equals=data.get("count_equals"),
            retrieval_must_include_types=tuple(types),
            no_leak=data.get("no_leak"),
            must_not_require_named_document=data.get("must_not_require_named_document"),
        )


@dataclass(frozen=True)
class CapabilityCase:
    capability_id: str
    case_id: str
    language: str
    question: str
    checks: CapabilityCheck = field(default_factory=CapabilityCheck)
    fixture: str | None = None
    gate_level: str = "l0_data"


@dataclass(frozen=True)
class CapabilityCaseResult:
    case_id: str
    capability_id: str
    status: str
    details: tuple[str, ...] = ()
