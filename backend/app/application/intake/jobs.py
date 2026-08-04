"""IntakeJobManager — the M1 background job framework (queue / progress /
pause / resume / cancel), with *no worker pool* yet by design.

Architecture contract (V2 §3, scoped down to M1):

- **The session object IS the durable job record.** Status, progress
  checkpoint, current stage and control flags all persist on the
  ``INTAKE_SESSION`` universal object, so a process crash loses at most the
  in-flight step — ``reconcile_interrupted`` marks the orphans ``failed`` and
  the resume endpoint continues them from their item cursors.
- **One dispatcher thread, FIFO.** Sessions are enqueued on create/resume and
  drained one at a time. Concurrency = 1 keeps SQLite single-writer-happy and
  makes pause/cancel checkpoints deterministic; scaling out later means
  growing *this* class behind its method surface, not re-architecting calls.
- **Cooperative control, never killed mid-write.** Pause/cancel flip flags
  that the runner probes between steps; the new state is persisted before the
  drain yields. ``mark_deleted`` aborts a live drain without write-back.
- **Immortal dispatcher.** A draining session that raises unexpectedly has
  already persisted its failure; the thread logs, discards, and takes the
  next job.

Framework-free: ``threading`` + ``queue`` from the stdlib, the repository
*factory* injected so every drain runs on its own session.
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from app.application.dtos.intake import (
    INTAKE_ACTOR,
    KEY_CURRENT_STAGE,
    KEY_ENDED_AT,
    KEY_ERROR,
    KEY_INTAKE_STATUS,
    IntakeSessionStatus,
    json_encode,
)
from app.application.intake.pipeline import utcnow_iso
from app.application.intake.runner import IntakeRunner
from app.application.ports.file_storage import FileStorage
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry

# How the factory hands a short-lived repository to one drain: a pair of the
# repository plus its cleanup callable (e.g. closing the DB session).
RepositoryFactory = Callable[[], tuple[ObjectRepository, Callable[[], None]]]

_GO = "go"
_PAUSE = "pause"
_CANCEL = "cancel"
_DELETED = "deleted"

_TRANSIENT_STATUSES = frozenset(
    {IntakeSessionStatus.QUEUED.value, IntakeSessionStatus.RUNNING.value}
)


class IntakeJobManager:
    """Single-dispatcher job framework for intake sessions."""

    def __init__(self, repository_factory: RepositoryFactory, storage: FileStorage) -> None:
        self._repository_factory = repository_factory
        self._storage = storage
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._flags: dict[str, dict[str, bool]] = {}
        self._enqueued: set[str] = set()
        self._active_id: str | None = None
        self._shutdown = False
        self._worker = threading.Thread(
            target=self._drain_loop, name="intake-dispatcher", daemon=True
        )
        self._worker.start()

    # ---------------------------------------------------------- control
    def _flags_locked(self, session_id: str) -> dict[str, bool]:
        """Fetch-or-create the control flag set. CALLER MUST HOLD ``_lock``."""

        return self._flags.setdefault(
            session_id, {"pause": False, "cancel": False, "deleted": False}
        )

    def enqueue(self, session_id: str) -> None:
        """Queue a session for draining (idempotent per pending drain)."""

        with self._lock:
            if self._shutdown:
                return
            flags = self._flags_locked(session_id)
            flags["pause"] = False
            flags["cancel"] = False
            flags["deleted"] = False
            if session_id in self._enqueued or self._active_id == session_id:
                return
            self._enqueued.add(session_id)
            self._queue.put(session_id)

    def request_pause(self, session_id: str) -> None:
        with self._lock:
            self._flags_locked(session_id)["pause"] = True

    def request_cancel(self, session_id: str) -> None:
        with self._lock:
            self._flags_locked(session_id)["cancel"] = True

    def mark_deleted(self, session_id: str) -> None:
        with self._lock:
            flags = self._flags_locked(session_id)
            flags["cancel"] = True
            flags["deleted"] = True

    def is_active(self, session_id: str) -> bool:
        with self._lock:
            return self._active_id == session_id

    def queued_count(self) -> int:
        with self._lock:
            return len(self._enqueued)

    def active_session(self) -> str | None:
        with self._lock:
            return self._active_id

    # ------------------------------------------------------- runner glue
    def _control_probe(self, session_id: str) -> Callable[[], str]:
        def probe() -> str:
            with self._lock:
                flags = self._flags.get(session_id)
            if not flags:
                return _GO
            if flags.get("deleted"):
                return _DELETED
            if flags.get("cancel"):
                return _CANCEL
            if flags.get("pause"):
                return _PAUSE
            return _GO

        return probe

    def _drain_loop(self) -> None:
        while True:
            session_id = self._queue.get()
            try:
                if session_id is None:  # shutdown sentinel
                    return
                with self._lock:
                    self._enqueued.discard(session_id)
                    self._active_id = session_id
                repository, cleanup = self._repository_factory()
                try:
                    runner = IntakeRunner(
                        repository, self._storage, session_id, self._control_probe(session_id)
                    )
                    runner.run()
                except Exception:  # noqa: BLE001 — runner already persisted;
                    # the dispatcher must never die with a job.
                    pass
                finally:
                    cleanup()
            finally:
                with self._lock:
                    if self._active_id == session_id:
                        self._active_id = None
                self._queue.task_done()

    # --------------------------------------------------------- reconcile
    def reconcile_interrupted(self) -> int:
        """Mark sessions left queued/running by a previous process as FAILED
        (resumable — the resume endpoint continues them). Returns the count."""

        repository, cleanup = self._repository_factory()
        try:
            sessions = repository.find(object_type=ObjectType.INTAKE_SESSION)
            count = 0
            for session in sessions:
                status = session.metadata.get_value(KEY_INTAKE_STATUS) or ""
                if status not in _TRANSIENT_STATUSES:
                    continue
                stage = session.metadata.get_value(KEY_CURRENT_STAGE) or "session"
                message = "Interrupted by an application restart — resume to continue."
                session.set_metadata(
                    MetadataEntry(
                        KEY_ERROR,
                        json_encode({"stage": stage, "message": message}),
                        MetadataLayer.L1_SYSTEM,
                        Provenance.SYSTEM,
                    ),
                    actor=INTAKE_ACTOR,
                )
                session.set_metadata(
                    MetadataEntry(
                        KEY_ENDED_AT, utcnow_iso(), MetadataLayer.L1_SYSTEM, Provenance.SYSTEM
                    ),
                    actor=INTAKE_ACTOR,
                )
                session.set_metadata(
                    MetadataEntry(
                        KEY_INTAKE_STATUS,
                        IntakeSessionStatus.FAILED.value,
                        MetadataLayer.L1_SYSTEM,
                        Provenance.SYSTEM,
                    ),
                    actor=INTAKE_ACTOR,
                )
                repository.save(session)
                count += 1
            return count
        finally:
            cleanup()

    # ---------------------------------------------------------- shutdown
    def shutdown(self, timeout: float = 10.0) -> None:
        """Stop the dispatcher thread (tests + app shutdown). In-flight drains
        persist their last checkpoint first; queued sessions stay resumable."""

        with self._lock:
            self._shutdown = True
        self._queue.put(None)
        self._worker.join(timeout=timeout)
