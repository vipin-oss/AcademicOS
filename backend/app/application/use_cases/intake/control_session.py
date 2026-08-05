"""Use cases: Pause / Resume / Cancel an intake session.

Transition guards live here (422 at the boundary, per the module doctrine);
the *durable* state change is persisted either by the dispatcher at its next
cooperative checkpoint (queued/running sessions) or immediately by the use
case when no drain is alive (paused sessions being cancelled, any resume).
"""

from __future__ import annotations

from app.application.commands.control_intake_session import ControlIntakeSessionCommand
from app.application.dtos.intake import (
    CANCELLABLE,
    KEY_CONTROL,
    KEY_ENDED_AT,
    KEY_ERROR,
    KEY_INTAKE_STATUS,
    KEY_SUMMARY,
    PAUSABLE,
    RESUMABLE,
    IntakeSessionOutput,
    IntakeSessionStatus,
    intake_session_status_of,
    json_decode,
    json_encode,
)
from app.application.exceptions import ValidationError
from app.application.intake.jobs import IntakeJobManager
from app.application.intake.pipeline import utcnow_iso
from app.application.use_cases.intake.helpers import (
    get_intake_session_or_404,
    items_of_session,
    session_view,
    set_system_metadata,
)
from app.domain.exceptions import OptimisticConcurrencyError
from app.domain.repositories.object_repository import ObjectRepository

# R3 — the drain writes the session row concurrently with control requests,
# so a control save can lose the optimistic-concurrency compare-and-swap to
# an in-flight progress write. Bounded retry: re-load the authoritative row
# and re-apply the (idempotent) control mutation. Exhaustion surfaces as
# OptimisticConcurrencyError (409 at the API).
_CONFLICT_RETRIES = 3


class PauseIntakeSessionUseCase:
    def __init__(self, repository: ObjectRepository, jobs: IntakeJobManager) -> None:
        self._repository = repository
        self._jobs = jobs

    def execute(self, command: ControlIntakeSessionCommand) -> IntakeSessionOutput:
        # Ordering invariant: this row write must COMMIT before the in-memory
        # pause flag exists. The drain's cooperative abort (``_persist_abort``)
        # fires only after the flag is observable, so its fresh-load merge —
        # which includes this ``control`` update — is always the LAST writer
        # of the session row. Flag-then-save inverted that order: on any
        # storage where this commit queues behind the drain's own commits,
        # the stale snapshot loaded above (status ``running``) landed AFTER
        # the abort persist and clobbered ``paused`` back to ``running`` —
        # a permanently wedged session (lease released, dispatcher idle,
        # no writer left to settle it).
        for attempt in range(_CONFLICT_RETRIES):
            obj = get_intake_session_or_404(self._repository, command.session_id)
            status = intake_session_status_of(obj)
            if status not in PAUSABLE:
                raise ValidationError(f"Cannot pause: session is {status.value}.")
            control = json_decode(obj.metadata.get_value(KEY_CONTROL), {})
            control["pause"] = True
            set_system_metadata(obj, KEY_CONTROL, json_encode(control))
            try:
                self._repository.save(obj)
            except OptimisticConcurrencyError:
                if attempt == _CONFLICT_RETRIES - 1:
                    raise
                continue  # a drain progress write landed between load and
                # save — re-load the authoritative row and re-apply.
            self._jobs.request_pause(str(obj.id))
            return session_view(obj, items_of_session(self._repository, str(obj.id)))


class ResumeIntakeSessionUseCase:
    def __init__(self, repository: ObjectRepository, jobs: IntakeJobManager) -> None:
        self._repository = repository
        self._jobs = jobs

    def execute(self, command: ControlIntakeSessionCommand) -> IntakeSessionOutput:
        for attempt in range(_CONFLICT_RETRIES):
            obj = get_intake_session_or_404(self._repository, command.session_id)
            status = intake_session_status_of(obj)
            if status not in RESUMABLE:
                raise ValidationError(f"Cannot resume: session is {status.value}.")
            control = json_decode(obj.metadata.get_value(KEY_CONTROL), {})
            set_system_metadata(
                obj, KEY_CONTROL, json_encode({**control, "pause": False, "cancel": False})
            )
            set_system_metadata(obj, KEY_ERROR, json_encode(None))
            set_system_metadata(obj, KEY_ENDED_AT, json_encode(None))
            set_system_metadata(obj, KEY_INTAKE_STATUS, IntakeSessionStatus.QUEUED.value)
            try:
                self._repository.save(obj)
            except OptimisticConcurrencyError:
                if attempt == _CONFLICT_RETRIES - 1:
                    raise
                continue
            self._jobs.enqueue(str(obj.id))
            return session_view(obj, items_of_session(self._repository, str(obj.id)))


class CancelIntakeSessionUseCase:
    def __init__(self, repository: ObjectRepository, jobs: IntakeJobManager) -> None:
        self._repository = repository
        self._jobs = jobs

    def execute(self, command: ControlIntakeSessionCommand) -> IntakeSessionOutput:
        for attempt in range(_CONFLICT_RETRIES):
            obj = get_intake_session_or_404(self._repository, command.session_id)
            status = intake_session_status_of(obj)
            if status not in CANCELLABLE:
                raise ValidationError(f"Cannot cancel: session is {status.value}.")
            self._jobs.request_cancel(str(obj.id))
            if status is not IntakeSessionStatus.PAUSED:
                # A drain is alive to notice the flag — nothing to persist.
                return session_view(obj, items_of_session(self._repository, str(obj.id)))
            # No drain is alive to notice the flag — persist immediately.
            set_system_metadata(obj, KEY_INTAKE_STATUS, IntakeSessionStatus.CANCELLED.value)
            set_system_metadata(obj, KEY_ENDED_AT, utcnow_iso())
            set_system_metadata(
                obj,
                KEY_SUMMARY,
                "Cancelled while paused. Start a new session to import the rest.",
            )
            try:
                self._repository.save(obj)
            except OptimisticConcurrencyError:
                if attempt == _CONFLICT_RETRIES - 1:
                    raise
                continue
            return session_view(obj, items_of_session(self._repository, str(obj.id)))
