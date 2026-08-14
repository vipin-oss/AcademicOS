"""Use case: L10 DLQ view — surface failed sessions and failed items.

The L10 DLQ formalizes the existing failed/reconcile state as a queryable,
actionable view — it does NOT create a second persistence system. The session
object and the item objects remain the durable job records; this use case
reads the FAILED sessions and ERROR items and exposes them with their
resume/reprocess target, so reconciliation can act on them.

Semantics (preserved from the existing intake contract):
- A FAILED session is resumable (resume continues from its item cursor).
- An ERROR item is isolated from healthy items (per-item isolation) and can be
  retried up to RETRY_LIMIT.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dtos.intake import (
    KEY_ATTEMPTS,
    KEY_ERROR,
    KEY_INTAKE_STATUS,
    KEY_RELATIVE_PATH,
    IntakeItemStatus,
    IntakeSessionStatus,
    json_decode,
)
from app.application.use_cases.intake.helpers import items_of_session
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


@dataclass(frozen=True)
class DeadLetterEntry:
    """One DLQ entry: a failed session or a failed item, actionable."""

    kind: str  # "session" | "item"
    id: str
    status: str
    session_id: str | None = None
    relative_path: str | None = None
    error: str = ""
    reason: str = ""
    attempts: int = 0
    retryable: bool = False
    resumable: bool = False


@dataclass(frozen=True)
class DeadLetterView:
    """The L10 DLQ query view (deterministic, sorted)."""

    sessions: tuple[DeadLetterEntry, ...] = ()
    items: tuple[DeadLetterEntry, ...] = ()
    total: int = 0


class ListDeadLetterUseCase:
    """Query the L10 dead-letter queue (failed sessions + failed items)."""

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, *, limit: int = 100) -> DeadLetterView:
        sessions = sorted(
            (
                s
                for s in self._repository.find(object_type=ObjectType.INTAKE_SESSION)
                if (s.metadata.get_value(KEY_INTAKE_STATUS) or "")
                == IntakeSessionStatus.FAILED.value
            ),
            key=lambda s: str(s.id),
        )
        session_entries = tuple(
            DeadLetterEntry(
                kind="session",
                id=str(s.id),
                status=IntakeSessionStatus.FAILED.value,
                session_id=str(s.id),
                error=_error_message(s),
                reason="failed_session",
                resumable=True,
            )
            for s in sessions[:limit]
        )

        item_entries: list[DeadLetterEntry] = []
        for s in self._repository.find(object_type=ObjectType.INTAKE_SESSION):
            for item in items_of_session(self._repository, str(s.id)):
                status = item.metadata.get_value(KEY_INTAKE_STATUS) or ""
                if status != IntakeItemStatus.ERROR.value:
                    continue
                item_entries.append(
                    DeadLetterEntry(
                        kind="item",
                        id=str(item.id),
                        status=status,
                        session_id=str(s.id),
                        relative_path=item.metadata.get_value(KEY_RELATIVE_PATH),
                        error=_error_message(item),
                        reason="failed_item",
                        attempts=_attempts(item),
                        retryable=True,
                    )
                )
                if len(item_entries) >= limit:
                    break
            if len(item_entries) >= limit:
                break
        item_entries.sort(key=lambda e: e.id)
        return DeadLetterView(
            sessions=session_entries,
            items=tuple(item_entries),
            total=len(session_entries) + len(item_entries),
        )


def _error_message(obj) -> str:
    raw = obj.metadata.get_value(KEY_ERROR)
    data = json_decode(raw, None)
    if isinstance(data, dict):
        return str(data.get("message") or "")
    return str(raw or "")


def _attempts(obj) -> int:
    try:
        return int(obj.metadata.get_value(KEY_ATTEMPTS) or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "DeadLetterEntry",
    "DeadLetterView",
    "ListDeadLetterUseCase",
]
