"""V3 M5 — rung-0 answering: confirmed-claims lookup before any retrieval/LLM.

The first rung of the Answering Ladder (blueprint §B1): a question that maps
to a known predicate is answered directly from **CONFIRMED** claims — indexed,
deterministic, ₹0, no retrieval, no LLM. This is the product's core
"answer from confirmed structured facts first" principle (blueprint A12).

Predicate matching is DATA-driven: the question's word tokens are matched
against the predicate catalogue's ``predicate_id`` tokens (ADR-019 registry —
data, not a routing rule). Only ``ClaimStatus.CONFIRMED`` claims are returned;
``AUTO_SUGGESTED`` / ``PROPOSED`` are never authoritative (A10). No LLM is
invoked anywhere in this module (asserted by test).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.application.knowledge.predicate_catalogue import CATALOGUE
from app.application.ports.claim_store import ClaimStore
from app.application.ports.permission import PermissionEvaluator
from app.domain.value_objects.claim import Claim
from app.domain.value_objects.enums import PermissionAction
from app.domain.value_objects.span import Span

#: Word tokens (Unicode letters/digits, no underscore) — sufficient for
#: matching English predicate ids against mixed English/Hinglish questions.
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True)
class Rung0Evidence:
    """One evidence anchor from a claim span (page / bbox provenance)."""

    span_kind: str
    source_id: str | None = None
    page: int | None = None
    bbox: tuple | None = None


@dataclass(frozen=True)
class Rung0Answer:
    """A deterministic rung-0 answer sourced from a single confirmed claim."""

    predicate_id: str
    value: str
    source_document_id: str
    source_version: int
    evidence: tuple[Rung0Evidence, ...] = field(default_factory=tuple)
    rung: int = 0
    source_class: str = "claims"

    def to_dict(self) -> dict:
        return {
            "answer": self.value,
            "rung": self.rung,
            "source_class": self.source_class,
            "predicate_id": self.predicate_id,
            "source_document_id": self.source_document_id,
            "evidence": [
                {
                    "span_kind": e.span_kind,
                    "source_id": e.source_id,
                    "page": e.page,
                    "bbox": list(e.bbox) if e.bbox is not None else None,
                }
                for e in self.evidence
            ],
        }


def _question_tokens(question: str) -> set[str]:
    return {t.lower() for t in _WORD_RE.findall(question or "")}


def _predicate_tokens(predicate_id: str) -> set[str]:
    return {t for t in predicate_id.split("_") if t}


def _claim_value_text(claim: Claim) -> str:
    """A human-facing rendering of a claim's value (deterministic, no LLM)."""
    value = claim.value if isinstance(claim.value, dict) else {}
    kind = value.get("kind")
    if kind == "money":
        amount = value.get("amount")
        return f"₹{amount:,.2f}" if isinstance(amount, int | float) else str(amount)
    if kind in ("date", "text"):
        return str(value.get("value", ""))
    # raw / unknown: fall back to the stored text, never fabricated.
    return str(value.get("text", ""))


def _evidence(spans: list[Span]) -> tuple[Rung0Evidence, ...]:
    out: list[Rung0Evidence] = []
    for span in spans:
        if span.page is None and span.bbox is None:
            continue
        out.append(
            Rung0Evidence(
                span_kind=span.kind.value,
                source_id=span.source_id,
                page=span.page,
                bbox=span.bbox,
            )
        )
    return tuple(out)


class Rung0ClaimAnswerer:
    """Deterministic confirmed-claims fast path (no LLM, no retrieval).

    Permission-aware: a claim is served only when the caller may READ its
    source scope (the same ``PermissionEvaluator`` contract the retrieval path
    uses — permission is a pre-filter, never a post-filter). When no evaluator
    is supplied, no claim is filtered (callers that do not yet enforce ACL may
    inject ``None``), matching the retrieval default.
    """

    def __init__(
        self,
        claim_store: ClaimStore,
        permission_evaluator: PermissionEvaluator | None = None,
    ) -> None:
        self._claim_store = claim_store
        self._permission_evaluator = permission_evaluator

    def answer(self, question: str, principal: dict | None = None) -> Rung0Answer | None:
        """Answer from a confirmed claim the principal may READ, or ``None``.

        ``principal`` is ``{"sub": ..., "roles": [...]}`` (the same shape the
        retrieval path uses). A claim whose ``acl_scope`` denies the principal
        is skipped, so rung-0 never leaks a restricted fact.
        """
        tokens = _question_tokens(question)
        if not tokens:
            return None

        for spec in CATALOGUE:
            predicate_tokens = _predicate_tokens(spec.predicate_id)
            if not predicate_tokens or not predicate_tokens.issubset(tokens):
                continue
            confirmed = self._claim_store.confirmed_by_predicate(spec.predicate_id)
            for claim, spans in confirmed:
                if self._permission_evaluator is not None and not self._permission_evaluator.can(
                    principal=principal,
                    scope=claim.acl_scope,
                    action=PermissionAction.READ,
                ):
                    continue
                return Rung0Answer(
                    predicate_id=claim.predicate_id,
                    value=_claim_value_text(claim),
                    source_document_id=claim.source_document_id,
                    source_version=claim.source_version,
                    evidence=_evidence(spans),
                )
        return None


__all__ = ["Rung0Answer", "Rung0ClaimAnswerer", "Rung0Evidence"]
