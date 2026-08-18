"""Claim Projection Service — projects confirmed claims into domain objects.

Addresses the critical product gap: when a professor confirms extracted fields,
those confirmed claims should become visible academic records (Events,
Publications, Research Projects, Committees, etc.) — not just sit in the claim
store invisible.

Lifecycle: Document → Extraction → Claim → Review → **Confirm → Projection →
Domain Object** → Search/Dashboard/Reports

Design principles:
- Fully idempotent: re-projecting the same confirmed claims never creates
  duplicate domain objects.
- Preserves source-document provenance (RELATED_TO edge).
- Preserves claim/decision history (claims stay in the store).
- Preserves ownership and tenant isolation (uses the claim's acl_scope).
- Handles corrected/superseded claims correctly: only CONFIRMED claims
  participate in projection; SUPERSEDED/REJECTED are ignored.
- Works for all supported domain mappings; reports unsupported types honestly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.application.ports.claim_store import ClaimStore
from app.application.services.domain_record_router import (
    ROUTABLE,
    DomainRecordRouter,
    RouteOutcome,
    _clean_event_title,
    _f,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.claim import Claim, ClaimStatus

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectionResult:
    """Outcome of projecting one document's confirmed claims."""
    document_id: str
    outcomes: tuple[RouteOutcome, ...] = field(default_factory=tuple)
    confirmed_claim_count: int = 0
    unsupported_types: tuple[str, ...] = ()
    status: str = "no_claims"  # "projected" | "no_claims" | "no_mapping" | "error"


class ClaimProjectionService:
    """Projects confirmed claims for a source document into domain objects.

    Called after confirmation (individual, bulk, or correction) to ensure that
    the professor's review actions create visible academic records.
    """

    def __init__(
        self,
        claim_store: ClaimStore,
        repository: ObjectRepository,
    ) -> None:
        self._claims = claim_store
        self._repo = repository

    def project_document(self, document_id: str, created_by: str) -> ProjectionResult:
        """Project all confirmed claims for a document into domain objects.

        Idempotent: the DomainRecordRouter already handles duplicate detection.
        Only CONFIRMED claims participate; SUPERSEDED/REJECTED/PROPOSED are
        filtered out.

        Args:
            document_id: The source document whose confirmed claims to project.
            created_by: The user who owns/is creating these records.

        Returns:
            ProjectionResult with routing outcomes.
        """
        # Gather all claims for this document
        all_claims = self._claims.by_source(document_id)
        if not all_claims:
            return ProjectionResult(
                document_id=document_id,
                status="no_claims",
            )

        # Filter to CONFIRMED claims only
        confirmed = [c for c in all_claims if c.status is ClaimStatus.CONFIRMED]
        if not confirmed:
            return ProjectionResult(
                document_id=document_id,
                status="no_claims",
                confirmed_claim_count=0,
            )

        # Build the fields dict from confirmed claims
        fields = self._fields_from_claims(confirmed)
        if not fields:
            return ProjectionResult(
                document_id=document_id,
                status="no_claims",
                confirmed_claim_count=len(confirmed),
            )

        # Determine the document type(s) from the claims' source document
        type_ids = self._infer_type_ids(all_claims)
        if not type_ids:
            # Try to infer from the claim predicate patterns
            type_ids = self._infer_type_from_fields(fields)

        if not type_ids:
            return ProjectionResult(
                document_id=document_id,
                status="no_mapping",
                confirmed_claim_count=len(confirmed),
            )

        # Check if the primary type is routable
        primary = type_ids[0]
        module = ROUTABLE.get(primary)
        if module is None:
            return ProjectionResult(
                document_id=document_id,
                status="no_mapping",
                confirmed_claim_count=len(confirmed),
                unsupported_types=(primary,),
            )

        # Safety: validate that sufficient domain-specific evidence exists
        # before attempting projection. This prevents accidental domain object
        # creation from stray predicates (e.g., journal_name from a venue
        # synonym overlap creating a Publication without publication_title).
        if not self._validate_sufficient_evidence(fields, module):
            return ProjectionResult(
                document_id=document_id,
                status="no_mapping",
                confirmed_claim_count=len(confirmed),
                unsupported_types=(primary,),
            )

        # Add __types__ marker for the router
        fields["__types__"] = type_ids

        # Route through the DomainRecordRouter (which handles duplicate detection)
        router = DomainRecordRouter(self._repo)
        try:
            outcomes = router.route(
                type_ids=type_ids,
                fields=fields,
                created_by=created_by,
                source_document_id=document_id,
                confidence=1.0,  # confirmed claims are authoritative
            )
        except Exception:
            _log.warning("Claim projection failed for document %s", document_id, exc_info=True)
            return ProjectionResult(
                document_id=document_id,
                status="error",
                confirmed_claim_count=len(confirmed),
            )

        return ProjectionResult(
            document_id=document_id,
            outcomes=tuple(outcomes),
            confirmed_claim_count=len(confirmed),
            status="projected",
        )

    def _fields_from_claims(self, claims: list[Claim]) -> dict[str, object]:
        """Build a predicate_id -> value dict from confirmed claims.

        For text values: uses the value['value'] field.
        For date values: uses the value['value'] field.
        For money values: uses the value['amount'] field.
        For number values: uses the value['value'] field.
        For raw values: uses the value['text'] field.
        """
        fields: dict[str, object] = {}
        for claim in claims:
            if not isinstance(claim.value, dict):
                continue
            kind = claim.value.get("kind")
            if kind == "text":
                fields[claim.predicate_id] = claim.value.get("value")
            elif kind == "date":
                fields[claim.predicate_id] = claim.value.get("value")
            elif kind == "money":
                fields[claim.predicate_id] = claim.value.get("amount")
            elif kind == "number":
                fields[claim.predicate_id] = claim.value.get("value")
            elif kind == "raw":
                fields[claim.predicate_id] = claim.value.get("text")
        # Filter out None values
        return {k: v for k, v in fields.items() if v is not None}

    def _infer_type_ids(self, claims: list[Claim]) -> tuple[str, ...]:
        """Infer document type_ids from claim predicates.

        Precedence rules (highest to lowest):
        1. Domain-DEFINING predicates: fields that are unique to one domain
           and required for entity creation (e.g., conference_name, publication_title,
           project_title, committee_name). These are STRONG signals.
        2. Domain-SPECIFIC predicates: fields that strongly indicate a domain
           but aren't unique (e.g., doi → publication, funding_agency → project).
        3. Weak/generic predicates: fields like journal_name, venue, start_date
           that appear across multiple domains. These NEVER trigger inference
           alone — they must be accompanied by at least one DEFINING predicate.

        The principle: a document gets projected into a domain ONLY when
        sufficient domain-specific evidence exists. One stray predicate
        (e.g., journal_name from a venue synonym overlap) must not override
        strong domain evidence (e.g., conference_name).
        """
        pred_ids = {c.predicate_id for c in claims}

        # --- Domain-DEFINING predicates (required for entity creation) ---
        # These are fields that are semantically unique to their domain and
        # are typically required fields in the extraction schema.

        # Conference: conference_name is the defining field
        conference_defining = {"conference_name"}
        # Publication: publication_title is the defining (required) field
        publication_defining = {"publication_title"}
        # Project: project_title is the defining (required) field
        project_defining = {"project_title"}
        # Committee: committee_name is the defining (required) field
        committee_defining = {"committee_name"}
        # Award: award_title is the defining (required) field
        award_defining = {"award_title"}
        # Notice/Event: event_title is the defining field
        notice_defining = {"event_title"}

        # --- Check for defining predicates first (highest priority) ---
        # When a defining predicate exists, the domain is unambiguous.

        if pred_ids & project_defining:
            return ("grant_sanction_letter", "grant", "research_project")

        if pred_ids & publication_defining:
            return ("publication",)

        if pred_ids & committee_defining:
            return ("committee",)

        if pred_ids & conference_defining:
            return ("conference_certificate", "conference")

        if pred_ids & award_defining:
            return ("award",)

        if pred_ids & notice_defining:
            return ("university_notice", "event")

        # --- Domain-SPECIFIC predicates (strong but not defining) ---
        # These indicate a domain but don't have the required title field.
        # We still route them — the DomainRecordRouter handles missing
        # required fields gracefully (returns 'skipped').

        # Project-specific (non-title)
        project_specific = {"sanctioned_amount", "funding_agency",
                           "sanction_order_number", "principal_investigator",
                           "project_duration_months"}
        if pred_ids & project_specific:
            return ("grant_sanction_letter", "grant", "research_project")

        # Conference-specific (non-title)
        conference_specific = {"conference_acronym", "conference_organizer",
                              "participation_type", "presentation_title",
                              "certificate_number"}
        if pred_ids & conference_specific:
            return ("conference_certificate", "conference")

        # Publication-specific (non-title): doi is highly specific to publications
        publication_specific = {"doi"}
        if pred_ids & publication_specific:
            return ("publication",)

        # Committee-specific (non-name)
        committee_specific = {"committee_members", "committee_role"}
        if pred_ids & committee_specific:
            return ("committee",)

        # --- Weak predicates: NEVER trigger inference alone ---
        # journal_name, authors, venue, start_date, end_date, etc. are
        # shared across domains. journal_name alone (without publication_title
        # or doi) is NOT sufficient evidence for publication projection.
        # Similarly, venue alone is not sufficient for any domain.

        return ()

    def _infer_type_from_fields(self, fields: dict[str, object]) -> tuple[str, ...]:
        """Infer document type_ids from the fields dict when claims aren't enough.

        Only uses DEFINING predicates — the required title/name fields.
        """
        if "conference_name" in fields:
            return ("conference_certificate", "conference")
        if "publication_title" in fields:
            return ("publication",)
        if "project_title" in fields:
            return ("grant_sanction_letter", "grant", "research_project")
        if "committee_name" in fields:
            return ("committee",)
        if "award_title" in fields:
            return ("award",)
        if "event_title" in fields:
            return ("university_notice", "event")
        return ()

    # Minimum predicates required per domain module for safe projection.
    # Each set contains the DEFINING predicate(s) that must be present.
    # A single generic predicate (e.g., journal_name) is never sufficient.
    _REQUIRED_EVIDENCE: dict[str, set[str]] = {
        "event": {"conference_name", "event_title"},
        "publication": {"publication_title"},
        "project": {"project_title", "sanction_order_number",
                    "sanctioned_amount", "funding_agency"},
        "committee": {"committee_name"},
    }

    def _validate_sufficient_evidence(
        self, fields: dict[str, object], module: str
    ) -> bool:
        """Check whether sufficient domain-specific evidence exists for projection.

        Prevents accidental domain object creation from stray predicates.
        For example, journal_name alone (without publication_title) must NOT
        create a Publication.

        Returns True when at least one required/defining predicate exists
        for the target module. Returns False when the evidence is too weak.
        """
        required = self._REQUIRED_EVIDENCE.get(module)
        if required is None:
            # No minimum requirement defined — allow projection (e.g., new module)
            return True
        return bool(required & set(fields.keys()))


__all__ = ["ClaimProjectionService", "ProjectionResult"]
