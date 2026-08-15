"""L3 CDM-block confirmation service (ADR-032).

Records durable human decisions (approve/reject) on CDM blocks WITHOUT modifying
the frozen L1 ``cdm_blocks`` schema (no status column). The decision audit lives
in ``cdm_decisions``; the block itself is unchanged. This keeps L1 boundaries
intact while providing an auditable confirmation surface for structural
candidates.
"""

from __future__ import annotations

from app.application.ports.cdm_decision_store import CdmDecisionStore
from app.application.services.decision_records import DecisionRecord, new_decision_id


class CdmConfirmationService:
    def __init__(self, decisions: CdmDecisionStore) -> None:
        self._decisions = decisions

    def approve(
        self, block_id: str, *, reviewer: str, notes: str = "",
        acl_scope: str | None = None,
    ) -> DecisionRecord:
        record = DecisionRecord(
            decision_id=new_decision_id(),
            subject_id=block_id,
            decision="approve",
            reviewer=reviewer,
            previous_status="proposed",
            resulting_status="confirmed",
            notes=notes,
            acl_scope=acl_scope,
        )
        return self._decisions.add(record)

    def reject(
        self, block_id: str, *, reviewer: str, notes: str = "",
        acl_scope: str | None = None,
    ) -> DecisionRecord:
        record = DecisionRecord(
            decision_id=new_decision_id(),
            subject_id=block_id,
            decision="reject",
            reviewer=reviewer,
            previous_status="proposed",
            resulting_status="rejected",
            notes=notes,
            acl_scope=acl_scope,
        )
        return self._decisions.add(record)
