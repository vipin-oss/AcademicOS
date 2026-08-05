"""Use case: Retry the failed items of an intake session (M2 Part 3).

Retry discipline (deterministic, no timers):

- Only *failed* items are retried — a retry drain re-processes exclusively
  items in ``error`` whose attempt count is below :data:`RETRY_LIMIT`;
  completed items are never touched, unsupported stays unsupported.
- Eligible sessions: ``completed`` (finished with errors) or ``failed``
  (systemic / crash-interrupted). ``queued``/``running``/``paused`` are the
  drain's own business (422), ``cancelled`` is terminal (422).
- Nothing retryable → honest 422 ("attempts exhausted" or "nothing failed"),
  the session state is left byte-identical.
"""
from __future__ import annotations

from app.application.commands.control_intake_session import ControlIntakeSessionCommand
from app.application.dtos.intake import (
    KEY_CONTROL,
    KEY_ENDED_AT,
    KEY_ERROR,
    KEY_INTAKE_STATUS,
    RETRY_LIMIT,
    IntakeItemStatus,
    IntakeSessionOutput,
    IntakeSessionStatus,
    intake_item_facts,
    intake_session_status_of,
    json_decode,
    json_encode,
)
from app.application.exceptions import ValidationError
from app.application.intake.jobs import IntakeJobManager
from app.application.use_cases.intake.helpers import (
    get_intake_session_or_404,
    items_of_session,
    session_view,
    set_system_metadata,
)
from app.domain.repositories.object_repository import ObjectRepository

#: Session statuses a retry drain may start from. PAUSED is deliberately
#: excluded — that transition is Resume's contract (422s here, honestly).
RETRYABLE_SESSION_STATUSES = frozenset(
    {IntakeSessionStatus.COMPLETED, IntakeSessionStatus.FAILED}
)


def retryable_item_count(items) -> int:
    """Failed items that still own at least one retry attempt."""

    count = 0
    for item in items:
        facts = intake_item_facts(item)
        if facts.status is IntakeItemStatus.ERROR and facts.attempts < RETRY_LIMIT:
            count += 1
    return count


class RetryIntakeSessionUseCase:
    def __init__(self, repository: ObjectRepository, jobs: IntakeJobManager) -> None:
        self._repository = repository
        self._jobs = jobs

    def execute(self, command: ControlIntakeSessionCommand) -> IntakeSessionOutput:
        obj = get_intake_session_or_404(self._repository, command.session_id)
        status = intake_session_status_of(obj)
        if status not in RETRYABLE_SESSION_STATUSES:
            raise ValidationError(f"Cannot retry: session is {status.value}.")
        items = items_of_session(self._repository, str(obj.id))
        retryable = retryable_item_count(items)
        if retryable == 0:
            raise ValidationError(
                "Nothing to retry: no failed items with attempts left "
                f"(retry limit is {RETRY_LIMIT})."
            )
        control = json_decode(obj.metadata.get_value(KEY_CONTROL), {})
        set_system_metadata(
            obj, KEY_CONTROL, json_encode({**control, "pause": False, "cancel": False})
        )
        set_system_metadata(obj, KEY_ERROR, json_encode(None))
        set_system_metadata(obj, KEY_ENDED_AT, json_encode(None))
        set_system_metadata(obj, KEY_INTAKE_STATUS, IntakeSessionStatus.QUEUED.value)
        self._repository.save(obj)
        self._jobs.enqueue(str(obj.id))
        return session_view(obj, items)
