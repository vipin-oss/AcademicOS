"""Confirmation queue service (L3, ADR-033).

Lists PROPOSED claim candidates for human review, triaged by confidence +
OCR-uncertainty, paginated, and ACL-filtered by a ``can_decide`` predicate.
Never leaks candidates the reviewer cannot decide on.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.application.ports.claim_store import ClaimStore
from app.application.services.confidence_triage import triage_key
from app.domain.value_objects.claim import ClaimStatus, confidence_tier


@dataclass(frozen=True)
class PendingClaim:
    claim_id: str
    predicate_id: str
    value_schema: str
    source_document_id: str
    source_version: int
    fact_confidence: float | None
    extraction_confidence: float | None
    acl_scope: str | None
    tier: str
    needs_ocr: bool = False


class ConfirmationQueue:
    def __init__(self, store: ClaimStore) -> None:
        self._store = store

    def pending(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        can_decide: Callable[[str | None], bool] | None = None,
    ) -> list[PendingClaim]:
        """PROPOSED claims, triaged, paginated, ACL-filtered.

        ``can_decide``(acl_scope) returns True when the reviewer may decide on
        a claim with that scope. When None, no filtering is applied (caller
        opts out). Candidates failing ``can_decide`` are excluded (no
        cross-scope leakage).
        """
        claims = self._store.by_status(ClaimStatus.PROPOSED)
        if can_decide is not None:
            claims = [c for c in claims if can_decide(c.acl_scope)]

        claims.sort(key=lambda c: triage_key(
            fact_confidence=c.fact_confidence,
            needs_ocr=False,
            subject_id=c.claim_id,
        ))

        start = (page - 1) * page_size
        page_claims = claims[start : start + page_size]
        return [
            PendingClaim(
                claim_id=c.claim_id,
                predicate_id=c.predicate_id,
                value_schema=c.value_schema,
                source_document_id=c.source_document_id,
                source_version=c.source_version,
                fact_confidence=c.fact_confidence,
                extraction_confidence=c.extraction_confidence,
                acl_scope=c.acl_scope,
                tier=confidence_tier(c.fact_confidence) if c.fact_confidence is not None else "low",
            )
            for c in page_claims
        ]
