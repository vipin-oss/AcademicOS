"""Bulk confirmation service (V3 M7, ADR-054 — review at scale).

"Confirm all suggested ≥ threshold" as ONE attributable, transactional, undoable
human action — NOT auto-approval (audit A10). Every claim confirmed here is a
separate, durable, human-attributed decision row (ADR-032), so the bulk action
is auditable and reversible through the same correction/reject paths as a
single-item decision. The caller owns the transaction: nothing is committed
here, so a failure rolls the whole batch back (atomic).

ACL gate: a claim is confirmed only if the reviewer may decide on its source
scope (``can_decide``); claims outside the reviewer's scopes are never touched.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.application.ports.claim_decision_store import ClaimDecisionStore
from app.application.ports.claim_store import ClaimStore
from app.application.services.decision_records import DecisionRecord
from app.domain.value_objects.claim import ClaimStatus

#: The blueprint's bulk-confirm confidence floor (≥ 0.95 = "suggested" high tier).
BULK_CONFIRM_MIN_CONFIDENCE = 0.95


@dataclass(frozen=True)
class BulkConfirmResult:
    """Outcome of one bulk confirmation run."""

    confirmed: int = 0
    skipped: int = 0
    decisions: tuple[DecisionRecord, ...] = field(default_factory=tuple)


class BulkConfirmationService:
    """Confirm every AUTO_SUGGESTED claim at/above a confidence floor, atomically."""

    def __init__(self, claims: ClaimStore, decisions: ClaimDecisionStore) -> None:
        self._claims = claims
        self._decisions = decisions
        # local import avoids a cycle (confirmation service -> claim service)
        from app.application.services.claim_confirmation import ClaimConfirmationService
        from app.application.services.claim_service import ClaimService

        self._confirmation = ClaimConfirmationService(ClaimService(claims), decisions)

    def confirm_suggested(
        self,
        *,
        reviewer: str,
        min_confidence: float = BULK_CONFIRM_MIN_CONFIDENCE,
        can_decide: Callable[[str | None], bool] | None = None,
        limit: int | None = None,
    ) -> BulkConfirmResult:
        """Confirm eligible AUTO_SUGGESTED claims, all attributable to ``reviewer``.

        A claim is eligible when: status AUTO_SUGGESTED, ``fact_confidence``
        present and >= ``min_confidence``, and (when ``can_decide`` is given)
        the reviewer may decide on its ``acl_scope``. Ineligible claims are
        skipped and counted, never silently confirmed.
        """
        suggested = self._claims.by_status(ClaimStatus.AUTO_SUGGESTED)
        eligible: list = []
        for claim in suggested:
            if claim.fact_confidence is None or claim.fact_confidence < min_confidence:
                continue
            if can_decide is not None and not can_decide(claim.acl_scope):
                continue
            eligible.append(claim)
        if limit is not None:
            eligible = eligible[:limit]

        decisions: list[DecisionRecord] = []
        for claim in eligible:
            record = self._confirmation.approve(
                claim.claim_id, reviewer=reviewer, notes="bulk-confirm"
            )
            decisions.append(record)

        return BulkConfirmResult(
            confirmed=len(decisions),
            skipped=len(suggested) - len(decisions),
            decisions=tuple(decisions),
        )


__all__ = [
    "BULK_CONFIRM_MIN_CONFIDENCE",
    "BulkConfirmResult",
    "BulkConfirmationService",
]
