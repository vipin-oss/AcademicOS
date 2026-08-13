"""L1 claim lifecycle service (ADR-002, ADR-006, ADR-019, ADR-021).

Coordinates the claim store with the predicate catalogue and the span model.
Engines (L2) call ``propose``; humans confirm/reject via ``confirm`` /
``reject``; the version-replacement cascade calls ``supersede_for_version``.

Facts vs metadata: engines write PROPOSED claims here; they never write object
metadata directly. Only CONFIRMED/ASSERTED claims are authoritative.
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.application.knowledge.predicate_catalogue import (
    get_predicate,
    normalize_predicate_value,
)
from app.application.ports.claim_store import ClaimStore
from app.domain.value_objects.claim import MEDIUM_CONFIDENCE_CAP, Claim, ClaimStatus
from app.domain.value_objects.enums import Provenance
from app.domain.value_objects.span import Span

#: OCR/vision-derived claims are capped at medium fact confidence (ADR-004).
OCR_DERIVED_CONFIDENCE_CAP = MEDIUM_CONFIDENCE_CAP


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class ClaimService:
    def __init__(self, store: ClaimStore) -> None:
        self._store = store

    def propose(
        self,
        *,
        predicate_id: str,
        raw_value: object,
        source_text: str,
        source_document_id: str,
        source_version: int,
        spans: list[Span],
        acl_scope: str | None,
        fact_confidence: float | None = None,
        extraction_confidence: float | None = None,
        provenance: Provenance = Provenance.INFERRED,
        ocr_derived: bool = False,
    ) -> Claim:
        """Create a PROPOSED claim bound to the predicate catalogue.

        Unknown/unparseable values are stored as ``raw`` with the source text
        (ADR-019) — never dropped. Fact confidence for OCR/vision-derived
        claims is capped at medium (ADR-004).
        """
        spec = get_predicate(predicate_id)
        if spec is None:
            value = {
                "kind": "raw",
                "text": source_text,
                "predicate_id": predicate_id,
                "reason": "unknown_predicate",
            }
            value_schema = "raw"
            predicate_version = 1
        else:
            value = normalize_predicate_value(predicate_id, raw_value, source_text)
            value_schema = spec.value_schema
            predicate_version = spec.version

        if ocr_derived and fact_confidence is not None:
            fact_confidence = min(fact_confidence, OCR_DERIVED_CONFIDENCE_CAP)

        claim = Claim(
            claim_id=f"claim:{uuid.uuid4().hex[:16]}",
            predicate_id=predicate_id,
            predicate_version=predicate_version,
            value_schema=value_schema,
            value=value,
            source_document_id=source_document_id,
            source_version=source_version,
            status=ClaimStatus.PROPOSED,
            provenance=provenance,
            fact_confidence=fact_confidence,
            extraction_confidence=extraction_confidence,
            acl_scope=acl_scope,
            spans=tuple(spans),
        )
        return self._store.put(claim, spans)

    def confirm(
        self,
        claim_id: str,
        *,
        reviewer: str | None = None,
        assert_human: bool = False,
    ) -> Claim:
        """Promote a claim to CONFIRMED (canonical). ``assert_human`` marks an
        ASSERTED human-asserted claim (immutable to machine writes, FR-MET-009)."""
        stored = self._store.get(claim_id)
        if stored is None:
            raise KeyError(f"Claim not found: {claim_id}")
        claim, _ = stored
        if claim.status is ClaimStatus.REJECTED:
            raise ValueError("Rejected claims cannot be promoted without a correction.")
        updated = Claim(
            claim_id=claim.claim_id,
            predicate_id=claim.predicate_id,
            predicate_version=claim.predicate_version,
            value_schema=claim.value_schema,
            value=claim.value,
            source_document_id=claim.source_document_id,
            source_version=claim.source_version,
            status=ClaimStatus.CONFIRMED,
            provenance=Provenance.ASSERTED if assert_human else claim.provenance,
            fact_confidence=claim.fact_confidence,
            extraction_confidence=claim.extraction_confidence,
            acl_scope=claim.acl_scope,
            supersedes_claim_id=claim.supersedes_claim_id,
            spans=claim.spans,
        )
        # Full upsert so provenance (ASSERTED for human confirmation) and the
        # preserved spans persist atomically (ADR-006 / FR-MET-009).
        self._store.put(updated, list(updated.spans))
        return updated

    def reject(
        self, claim_id: str, *, reviewer: str | None = None
    ) -> Claim:
        stored = self._store.get(claim_id)
        if stored is None:
            raise KeyError(f"Claim not found: {claim_id}")
        return self._store.set_status(
            claim_id, ClaimStatus.REJECTED, reviewer=reviewer, now=_utcnow_iso()
        )

    def supersede_claim(self, claim_id: str, by_claim_id: str) -> Claim:
        """Supersede one claim by another (ADR-021, no delete)."""
        return self._store.supersede(claim_id, by_claim_id, now=_utcnow_iso())

    def correct(
        self,
        claim_id: str,
        *,
        reviewer: str,
        raw_value: object,
        source_text: str = "",
        notes: str = "",
    ) -> Claim:
        """Create a new ASSERTED claim (human value) that SUPERSEDES the
        candidate ``claim_id`` (ADR-006 / ADR-021 correction-as-data).

        The original candidate is preserved (SUPERSEDED); the correction is a
        new authoritative fact, never a destructive edit of history.
        """
        stored = self._store.get(claim_id)
        if stored is None:
            raise KeyError(f"Claim not found: {claim_id}")
        candidate, _ = stored

        corrected = self.propose(
            predicate_id=candidate.predicate_id,
            raw_value=raw_value,
            source_text=source_text,
            source_document_id=candidate.source_document_id,
            source_version=candidate.source_version,
            spans=list(candidate.spans),
            acl_scope=candidate.acl_scope,
            fact_confidence=1.0,  # human-asserted correction
            extraction_confidence=candidate.extraction_confidence,
            provenance=Provenance.ASSERTED,
        )
        # Supersede the candidate by the correction.
        self._store.supersede(claim_id, corrected.claim_id, now=_utcnow_iso())
        return corrected

    def supersede_for_source_version(
        self,
        source_document_id: str,
        old_version: int,
        new_version: int,
    ) -> int:
        """Supersede every active claim of an old source version by a NEW
        placeholder claim for the new version (ADR-021 cascade).

        Returns the number of claims superseded. Nothing is deleted.
        """
        claims = self._store.for_source_version(source_document_id, old_version)
        for claim in claims:
            if claim.status is ClaimStatus.SUPERSEDED:
                continue
            # A new PROPOSED claim on the new version supersedes the old one;
            # re-extraction (L2) proposes the actual new value.
            replacement = self.propose(
                predicate_id=claim.predicate_id,
                raw_value=claim.value,
                source_text="",
                source_document_id=source_document_id,
                source_version=new_version,
                spans=[],
                acl_scope=claim.acl_scope,
                provenance=claim.provenance,
            )
            self._store.supersede(
                claim.claim_id, replacement.claim_id, now=_utcnow_iso()
            )
        return len(claims)
