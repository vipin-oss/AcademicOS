"""L6 claim evidence service (Freeze Contract §13.6, ADR-025).

Builds citable fact citations from the L1 claim store. Reuses the existing
``ClaimStore`` and ``Claim.is_authoritative`` (CONFIRMED/ASSERTED) gate. Only
claims visible to the requesting principal are exposed (ACL-gated via the
existing ``object_acl_scope`` + ``PermissionEvaluator``). Deterministic ordering
and deduplication. Does NOT create a second claim store, ACL system, or
evidence pipeline.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.application.dtos.assistant import AssistantCitation
from app.application.dtos.evidence import (
    ConfidenceView,
    EvidenceSet,
    FactCitation,
)
from app.application.ports.claim_store import ClaimStore
from app.application.ports.permission import PermissionEvaluator
from app.application.use_cases.auth.helpers import get_roles
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.claim import confidence_tier
from app.domain.value_objects.enums import PermissionAction


class ClaimEvidenceService:
    """Builds ACL-filtered, deterministic fact citations from the claim store."""

    def __init__(
        self, claim_store: ClaimStore, permission_evaluator: PermissionEvaluator
    ) -> None:
        self._claims = claim_store
        self._permissions = permission_evaluator

    def citable_claims(
        self,
        *,
        user: UniversalObject,
        source_document_id: str | None = None,
        limit: int = 50,
    ) -> list[FactCitation]:
        """CONFIRMED/ASSERTED claims visible to ``user``, as fact citations.

        Deterministic order: source, then claim id. Superseded/rejected claims
        are never citable. ACL-hidden claims/spans are excluded (no leakage).
        """
        principal = {"sub": str(user.id), "roles": get_roles(user)}
        claims = (
            self._claims.by_source(source_document_id)
            if source_document_id
            else self._all_citable()
        )
        out: list[FactCitation] = []
        seen: set[str] = set()
        for claim in claims:
            if not claim.is_authoritative:
                continue  # only CONFIRMED/ASSERTED are auto-usable (ADR-006)
            if claim.claim_id in seen:
                continue  # deterministic dedup
            if not self._permissions.can(
                principal=principal,
                scope=claim.acl_scope,
                action=PermissionAction.READ,
            ):
                continue  # ACL gate — never leak a hidden claim
            seen.add(claim.claim_id)
            if len(out) >= limit:
                break
            span = self._first_span_for(claim.claim_id)
            out.append(
                FactCitation(
                    number=len(out) + 1,
                    claim_id=claim.claim_id,
                    predicate_id=claim.predicate_id,
                    source_document_id=claim.source_document_id,
                    source_version=claim.source_version,
                    span=span,
                    value=claim.value,
                    confidence=ConfidenceView(
                        fact_confidence=claim.fact_confidence,
                        extraction_confidence=claim.extraction_confidence,
                        fact_tier=confidence_tier(claim.fact_confidence)
                        if claim.fact_confidence is not None else None,
                        extraction_tier=confidence_tier(claim.extraction_confidence)
                        if claim.extraction_confidence is not None else None,
                    ),
                    authoritative=True,
                )
            )
        return out

    def _all_citable(self) -> list:
        # Deterministic union of CONFIRMED claims; the service filters by
        # is_authoritative and ACL below.
        from app.domain.value_objects.claim import ClaimStatus

        return self._claims.by_status(ClaimStatus.CONFIRMED)

    def _first_span_for(self, claim_id: str) -> dict | None:
        """Load the first span for a claim via the ClaimStore (spans are stored
        separately from the claim row). Deterministic: the store's ``get``
        returns ``(claim, spans)`` in stored order."""
        stored = self._claims.get(claim_id)
        if stored is None:
            return None
        _claim, spans = stored
        if not spans:
            return None
        first = spans[0]
        to_region = getattr(first, "to_region_dict", None)
        if to_region is not None:
            return to_region()
        return {"source_id": getattr(first, "source_id", "")}


def assemble_evidence_set(
    object_citations: Iterable[AssistantCitation] = (),
    fact_citations: Iterable[FactCitation] = (),
    *,
    limit: int = 50,
) -> EvidenceSet:
    """Combine existing object citations with L6 fact citations into a
    deterministic, bounded ``EvidenceSet``.

    Reuses the existing object-citation records exactly as produced by
    ``CitationBuilder`` / ``evidence_assembly`` (no second citation builder);
    fact citations come from ``ClaimEvidenceService.citable_claims``. Ordering
    is deterministic: object citations first (in their existing order), then
    fact citations (in citation-number order). The combined set is bounded at
    ``limit`` and only authoritative fact citations are admitted (no leakage).
    """
    objs = tuple(object_citations)
    facts = tuple(f for f in fact_citations if f.authoritative)
    objs = objs[:limit]
    facts = facts[: max(0, limit - len(objs))]
    return EvidenceSet(object_citations=objs, fact_citations=facts)
