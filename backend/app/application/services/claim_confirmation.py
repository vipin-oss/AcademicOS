"""L3 claim confirmation/correction service (ADR-032).

Wraps the L1 ``ClaimService`` and adds durable, attributable decision audit.
Approve→CONFIRMED/ASSERTED; reject→REJECTED; correct→new ASSERTED superseding
the candidate. Every action writes an idempotent decision row and is ACL-gated
by the caller (the route enforces the source scope).
"""

from __future__ import annotations

from app.application.ports.claim_decision_store import ClaimDecisionStore
from app.application.services.claim_service import ClaimService
from app.application.services.decision_records import (
    DecisionRecord,
    new_decision_id,
)
from app.domain.value_objects.claim import ClaimStatus


class ClaimConfirmationService:
    def __init__(
        self, claims: ClaimService, decisions: ClaimDecisionStore
    ) -> None:
        self._claims = claims
        self._decisions = decisions

    def approve(
        self, claim_id: str, *, reviewer: str, notes: str = "",
        eval_run_id: str | None = None,
    ) -> DecisionRecord:
        claim = self._claims.confirm(claim_id, reviewer=reviewer, assert_human=True)
        record = DecisionRecord(
            decision_id=new_decision_id(),
            subject_id=claim_id,
            decision="approve",
            reviewer=reviewer,
            previous_status=ClaimStatus.PROPOSED.value,
            resulting_status=ClaimStatus.CONFIRMED.value,
            notes=notes,
            acl_scope=claim.acl_scope,
            eval_run_id=eval_run_id,
        )
        return self._decisions.add(record)

    def reject(
        self, claim_id: str, *, reviewer: str, notes: str = "",
        eval_run_id: str | None = None,
    ) -> DecisionRecord:
        claim = self._claims.reject(claim_id, reviewer=reviewer)
        record = DecisionRecord(
            decision_id=new_decision_id(),
            subject_id=claim_id,
            decision="reject",
            reviewer=reviewer,
            previous_status=claim.status.value,
            resulting_status=ClaimStatus.REJECTED.value,
            notes=notes,
            acl_scope=claim.acl_scope,
            eval_run_id=eval_run_id,
        )
        return self._decisions.add(record)

    def correct(
        self, claim_id: str, *, reviewer: str, raw_value: object,
        source_text: str = "", notes: str = "",
    ) -> DecisionRecord:
        corrected = self._claims.correct(
            claim_id, reviewer=reviewer, raw_value=raw_value, source_text=source_text
        )
        record = DecisionRecord(
            decision_id=new_decision_id(),
            subject_id=claim_id,
            decision="correct",
            reviewer=reviewer,
            previous_status=ClaimStatus.PROPOSED.value,
            resulting_status=ClaimStatus.SUPERSEDED.value,
            notes=notes,
            acl_scope=corrected.acl_scope,
        )
        return self._decisions.add(record)
