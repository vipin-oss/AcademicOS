"""Typed claim extraction (V3 M6, ADR-053).

The M6 answering step ``classify -> template -> candidates`` as a service:

1. classify the document's semantic type (:class:`DocumentClassifier`);
2. look up its extraction template (the allowed predicate set);
3. extract deterministic "Label: value" candidates from the text, restricted
   to the template's predicates (unknown type -> unrestricted, best-effort);
4. propose each candidate as a PROPOSED claim — or AUTO_SUGGESTED when the
   predicate passes its measured precision gate (A10 / ADR-006: suggestion is
   a review shortcut, never authoritative).

Deterministic only: no LLM, no strong model, no network. The existing
``NirMapper.write_claims`` path (tables/sheets/metadata) is unchanged; this is
the additive Wave-1 surface for free-form letters and orders.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.nir import NirDocument
from app.application.knowledge.extraction_templates import template_predicates
from app.application.services.claim_service import ClaimService
from app.application.services.document_classifier import (
    ClassificationResult,
    DocumentClassifier,
)
from app.application.services.fact_extraction import candidate_from_text_lines
from app.application.services.suggestion_policy import (
    AUTO_SUGGEST_CONFIDENCE,
    SuggestionPolicy,
)
from app.domain.value_objects.claim import Claim
from app.domain.value_objects.span import Span


@dataclass(frozen=True)
class TypedExtractionResult:
    document_type_id: str | None
    classification: ClassificationResult
    proposed: tuple[Claim, ...] = ()
    suggested: tuple[Claim, ...] = ()

    @property
    def claims(self) -> tuple[Claim, ...]:
        return self.proposed + self.suggested


class TypedClaimExtractor:
    """Classify a document and propose claims for its template's predicates."""

    def __init__(
        self,
        claim_service: ClaimService,
        classifier: DocumentClassifier | None = None,
        policy: SuggestionPolicy | None = None,
    ) -> None:
        self._claim_service = claim_service
        self._classifier = classifier or DocumentClassifier()
        self._policy = policy or SuggestionPolicy()

    def extract(
        self,
        nir: NirDocument,
        *,
        filename: str = "",
        document_id: str,
        acl_scope: str | None = None,
        ocr_derived: bool = False,
        spans: list[Span] | None = None,
    ) -> TypedExtractionResult:
        """Classify + extract claims for a parsed document.

        ``spans`` default to the NIR's element spans (page/bbox evidence).
        """
        classification = self._classifier.classify(nir.text, filename)
        allowed = template_predicates(classification.document_type_id)

        candidates = candidate_from_text_lines(nir.text)
        if allowed:
            candidates = [c for c in candidates if c.predicate_id in allowed]

        if spans is None:
            from app.application.services.nir_mapper import NirMapper

            spans = NirMapper.element_spans(nir)

        proposed: list[Claim] = []
        suggested: list[Claim] = []
        for cand in candidates:
            confidence = cand.fact_confidence or 0.0
            if (
                self._policy.allows_auto_suggest(cand.predicate_id)
                and confidence >= AUTO_SUGGEST_CONFIDENCE
            ):
                claim = self._claim_service.suggest(
                    predicate_id=cand.predicate_id,
                    raw_value=cand.raw_value,
                    source_text=cand.source_text,
                    source_document_id=document_id,
                    source_version=nir.version,
                    spans=spans,
                    acl_scope=acl_scope,
                    fact_confidence=cand.fact_confidence,
                    extraction_confidence=cand.extraction_confidence,
                    ocr_derived=ocr_derived,
                )
                suggested.append(claim)
            else:
                claim = self._claim_service.propose(
                    predicate_id=cand.predicate_id,
                    raw_value=cand.raw_value,
                    source_text=cand.source_text,
                    source_document_id=document_id,
                    source_version=nir.version,
                    spans=spans,
                    acl_scope=acl_scope,
                    fact_confidence=cand.fact_confidence,
                    extraction_confidence=cand.extraction_confidence,
                    ocr_derived=ocr_derived,
                )
                proposed.append(claim)

        return TypedExtractionResult(
            document_type_id=classification.document_type_id,
            classification=classification,
            proposed=tuple(proposed),
            suggested=tuple(suggested),
        )


__all__ = ["TypedClaimExtractor", "TypedExtractionResult"]
