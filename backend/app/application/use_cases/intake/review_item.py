"""Use case: human review of intake items (M9 — the Commit Engine gate).

One reviewer action per item:

- **approve** — persists the durable review decision, ensures a reviewed
  proposal exists (auto-generates from the item's real facts when the
  pipeline produced none), and commits the item through the existing
  Commit Engine: the Document is created (stored blob, BELONGS_TO edge,
  outbox events), the item becomes COMMITTED, and the caller is expected
  to drain the search index afterwards (the route does it — search is
  immediately fresh). Committing is idempotent-guarded by the engine.
- **reject** — persists the review decision and moves the item to the
  terminal REJECTED status; a rejected item can never be committed.

**bulk** applies one decision to every AWAITING_REVIEW item of a session
(or an explicit subset), reporting per-item outcomes so partial failures
are visible instead of swallowed.

Review decisions are persisted as system-layer item metadata
(``intake.review_decision``), the same durable-fact doctrine as the
committed-document pointer.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.intake import (
    KEY_INTAKE_STATUS,
    KEY_PROPOSAL,
    KEY_REVIEW_DECISION,
    KEY_SESSION_ID,
    IntakeItemStatus,
    IntakeSessionStatus,
    intake_session_status_of,
    json_decode,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.intake.commit_engine import CommitEngineService
from app.application.intake.proposal_engine import ProposalEngineService
from app.application.ports.file_storage import FileStorage
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId

REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"
REVIEW_DECISIONS = (REVIEW_APPROVED, REVIEW_REJECTED)


@dataclass(frozen=True)
class BulkReviewItem:
    """One item's outcome inside a bulk review."""

    item_id: str
    status: str  # committed | rejected | awaiting_review (unchanged on failure)
    document_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class BulkReviewResult:
    items: tuple[BulkReviewItem, ...] = field(default_factory=tuple)

    @property
    def succeeded(self) -> int:
        return sum(1 for i in self.items if i.error is None)


def _system_entry(key: str, value: str) -> MetadataEntry:
    return MetadataEntry(key, value, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


class ReviewItemUseCase:
    """The single review seam: approve/reject one item, or bulk-review a
    session. Approval delegates to the existing Commit Engine."""

    def __init__(self, repository: ObjectRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._commit_engine = CommitEngineService(repository, storage)
        self._proposal_engine = ProposalEngineService(repository)

    # ------------------------------------------------------------------ item
    def approve(self, item_id: str, actor: str):
        """Approve + commit one item (idempotent via the engine's guards)."""
        item = self._require_awaiting(item_id)
        self._ensure_proposal(item_id)
        item.set_metadata(
            _system_entry(KEY_REVIEW_DECISION, REVIEW_APPROVED), actor=actor
        )
        self._repository.save(item)
        return self._commit_engine.commit_item(item_id=item_id, actor=actor)

    def reject(self, item_id: str, actor: str) -> None:
        """Reject one item: terminal REJECTED, never committable."""
        item = self._require_awaiting(item_id)
        item.set_metadata(
            _system_entry(KEY_REVIEW_DECISION, REVIEW_REJECTED), actor=actor
        )
        item.set_metadata(
            _system_entry(KEY_INTAKE_STATUS, IntakeItemStatus.REJECTED.value),
            actor=actor,
        )
        self._repository.save(item)

    # ----------------------------------------------------------------- bulk
    def bulk(
        self,
        session_id: str,
        decision: str,
        actor: str,
        item_ids: list[str] | None = None,
    ) -> BulkReviewResult:
        """Apply ``decision`` to the session's awaiting items (or the given
        subset). Partial failures are reported per item, never raised."""
        if decision not in REVIEW_DECISIONS:
            raise ValidationError(
                f"decision must be one of: {', '.join(REVIEW_DECISIONS)}."
            )
        session = self._repository.get_by_id(ObjectId(session_id))
        if session is None or session.object_type is not ObjectType.INTAKE_SESSION:
            raise ObjectNotFoundError(f"Intake session not found: {session_id}")
        if intake_session_status_of(session) is not IntakeSessionStatus.COMPLETED:
            raise ValidationError("Session must be completed before reviewing items.")

        targets = item_ids or self._awaiting_item_ids(session_id)
        outcomes: list[BulkReviewItem] = []
        for target in targets:
            try:
                if decision == REVIEW_APPROVED:
                    out = self.approve(target, actor)
                    outcomes.append(
                        BulkReviewItem(
                            item_id=target,
                            status=IntakeItemStatus.COMMITTED.value,
                            document_id=out.document_id or None,
                        )
                    )
                else:
                    self.reject(target, actor)
                    outcomes.append(
                        BulkReviewItem(item_id=target, status=IntakeItemStatus.REJECTED.value)
                    )
            except (ValidationError, ObjectNotFoundError, ObjectAlreadyExistsError) as exc:
                outcomes.append(
                    BulkReviewItem(item_id=target, status="unchanged", error=str(exc))
                )
        return BulkReviewResult(items=tuple(outcomes))

    # --------------------------------------------------------------- helpers
    def _require_awaiting(self, item_id: str):
        item = self._repository.get_by_id(ObjectId(item_id))
        if item is None or item.object_type is not ObjectType.INTAKE_ITEM:
            raise ObjectNotFoundError(f"Intake item not found: {item_id}")
        status = item.metadata.get_value(KEY_INTAKE_STATUS)
        if status != IntakeItemStatus.AWAITING_REVIEW.value:
            raise ValidationError(
                f"Only awaiting-review items can be reviewed (item is {status!r})."
            )
        return item

    def _ensure_proposal(self, item_id: str) -> None:
        """A reviewed proposal is the commit gate; auto-generate one from
        the item's real facts when the pipeline produced none."""
        item = self._repository.get_by_id(ObjectId(item_id))
        raw = item.metadata.get_value(KEY_PROPOSAL) if item else None
        data = json_decode(raw, None)
        if not isinstance(data, dict) or not data.get("title"):
            self._proposal_engine.generate(item_id)

    def _awaiting_item_ids(self, session_id: str) -> list[str]:
        objs = self._repository.find_by_metadata(
            KEY_INTAKE_STATUS, IntakeItemStatus.AWAITING_REVIEW.value
        )
        ids = []
        for obj in objs:
            if obj.object_type is not ObjectType.INTAKE_ITEM:
                continue
            if (obj.metadata.get_value(KEY_SESSION_ID) or "") == session_id:
                ids.append(str(obj.id))
        return sorted(ids)


__all__ = [
    "BulkReviewItem",
    "BulkReviewResult",
    "REVIEW_APPROVED",
    "REVIEW_DECISIONS",
    "REVIEW_REJECTED",
    "ReviewItemUseCase",
]
