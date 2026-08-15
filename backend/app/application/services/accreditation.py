"""Accreditation workflow kernel (V3 M18, ADR-065).

Criterion → indicator → evidence requirement → submission → review → approval
→ period lock → export. The commercial differentiator.

The HARD authority boundary (blueprint + A10): AI may SUGGEST evidence and
DRAFT narratives, but it may NEVER approve evidence or lock a period — those
are human attestations (``approved_by`` / ``locked_by`` are always a human
identity, enforced by the service signature, not by convention).

Reuses the review discipline of the L3 confirmation adapters: approval is a
durable, attributable decision; a locked period is irreversible.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.knowledge.accreditation_frameworks import get_framework
from app.application.ports.accreditation_store import AccreditationStore, Submission

#: Lifecycle statuses.
STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


@dataclass(frozen=True)
class EvidenceSuggestion:
    """An AI-suggested piece of evidence (NEVER an approval)."""

    indicator_id: str
    suggested_document_ids: tuple[str, ...]
    draft_narrative: str = ""


class AccreditationWorkflow:
    """Submit, review, approve, and lock accreditation evidence."""

    def __init__(self, store: AccreditationStore) -> None:
        self._store = store

    def submit(
        self,
        *,
        framework_id: str,
        criterion_id: str,
        indicator_id: str,
        evidence: list[str],
        narrative: str = "",
        period: str = "",
    ) -> Submission:
        framework = get_framework(framework_id)
        if framework is None:
            raise ValueError(f"Unknown framework: {framework_id}")
        return self._store.add(
            Submission(
                id=uuid.uuid4().hex,
                framework_id=framework_id,
                criterion_id=criterion_id,
                indicator_id=indicator_id,
                status=STATUS_DRAFT,
                evidence=json.dumps(evidence),
                narrative=narrative,
                period=period,
                created_at=datetime.now(UTC).isoformat(),
            )
        )

    def submit_for_review(self, submission_id: str) -> Submission:
        return self._store.set_status(submission_id, STATUS_SUBMITTED)

    def approve(self, submission_id: str, *, reviewer: str) -> Submission:
        """HUMAN approval — the only path to APPROVED (AI can never call this)."""
        return self._store.set_status(submission_id, STATUS_APPROVED, approved_by=reviewer)

    def reject(self, submission_id: str, *, reviewer: str) -> Submission:
        return self._store.set_status(submission_id, STATUS_REJECTED, approved_by=reviewer)

    def lock_period(self, submission_id: str, *, locked_by: str) -> Submission:
        """HUMAN period lock — irreversible attestation (AI can never call this)."""
        submission = self._store.get(submission_id)
        if submission is None:
            raise KeyError(f"Submission not found: {submission_id}")
        if submission.status != STATUS_APPROVED:
            raise ValueError("Only an approved submission can lock a period.")
        return self._store.lock_period(submission_id, locked_by=locked_by)

    # --- AI suggestion (READ-ONLY; never approves, never locks) ------------
    @staticmethod
    def suggest_evidence(
        *,
        indicator_id: str,
        candidate_document_ids: list[str],
    ) -> EvidenceSuggestion:
        """Propose evidence + a draft narrative. Returns a SUGGESTION only —
        this method has no store access and cannot mutate state."""
        return EvidenceSuggestion(
            indicator_id=indicator_id,
            suggested_document_ids=tuple(candidate_document_ids),
            draft_narrative=f"Evidence gathered for {indicator_id}: "
            f"{len(candidate_document_ids)} supporting document(s).",
        )


__all__ = [
    "STATUS_APPROVED",
    "STATUS_DRAFT",
    "STATUS_REJECTED",
    "STATUS_SUBMITTED",
    "AccreditationWorkflow",
    "EvidenceSuggestion",
]
