"""Use case: Delete an intake session (items, staged blobs, session object).

Safety: a live drain is first signalled cancel + deleted, so its next
cooperative checkpoint aborts *without* writing back over the removed rows.
Blobs are deleted best-effort per recorded staging key (and, since M2, per
recorded extraction-text key) — both prefixes are per-session, so nothing
else can own those keys.
"""
from __future__ import annotations

from app.application.commands.delete_intake_session import DeleteIntakeSessionCommand
from app.application.dtos.intake import KEY_EXTRACTED_KEY, KEY_STAGED_KEY
from app.application.intake.jobs import IntakeJobManager
from app.application.ports.file_storage import FileStorage
from app.application.use_cases.intake.helpers import (
    get_intake_session_or_404,
    items_of_session,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.object_id import ObjectId


class DeleteIntakeSessionUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        storage: FileStorage,
        jobs: IntakeJobManager,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._jobs = jobs

    def execute(self, command: DeleteIntakeSessionCommand) -> None:
        obj = get_intake_session_or_404(self._repository, command.session_id)
        session_id = str(obj.id)

        # Stop any in-flight drain cooperatively, without write-back.
        self._jobs.request_cancel(session_id)
        self._jobs.mark_deleted(session_id)

        for item in items_of_session(self._repository, session_id):
            for key in (
                item.metadata.get_value(KEY_STAGED_KEY),
                item.metadata.get_value(KEY_EXTRACTED_KEY),
            ):
                if key and self._storage.exists(key):
                    try:
                        self._storage.delete(key)
                    except Exception:  # noqa: BLE001 — blob cleanup is best-effort;
                        # object deletion must not fail on a filesystem hiccup.
                        pass
            self._repository.delete(item.id)
        self._repository.delete(ObjectId(session_id))
