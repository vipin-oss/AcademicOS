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

M2 Part 3 (queue & recovery): every drain additionally holds a **durable
single-worker lease** (``intake.worker``) on the session row. The lease is
the deterministic answer to three failure modes: a second manager racing to
drain the same session (acquire verifies ownership after write), a process
dying mid-drain (heartbeat goes stale → another manager's reconcile or
resume may adopt), and double-processing (the runner only runs while leased).
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import queue
import socket
import threading
import uuid
from collections.abc import Callable

from app.application.dtos.intake import (
    INTAKE_ACTOR,
    KEY_CURRENT_STAGE,
    KEY_ENDED_AT,
    KEY_ERROR,
    KEY_INTAKE_STATUS,
    KEY_LEASE,
    IntakeSessionStatus,
    json_decode,
    json_encode,
)
from app.application.intake.pipeline import utcnow_iso
from app.application.intake.runner import IntakeRunner
from app.application.ports.document_parser import DocumentParsers
from app.application.ports.file_storage import FileStorage
from app.domain.entities.object import UniversalObject
from app.domain.exceptions import OptimisticConcurrencyError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId

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

_log = logging.getLogger(__name__)


def _lease_entry(value: dict | None) -> MetadataEntry:
    return MetadataEntry(KEY_LEASE, json_encode(value), MetadataLayer.L1_SYSTEM, Provenance.SYSTEM)


class IntakeJobManager:
    """Bounded worker-pool job framework for intake sessions (L10).

    L10 extends the original single-dispatcher design into a bounded stdlib
    worker pool *behind the same method surface and job semantics*. The durable
    worker lease, cooperative pause/cancel, retry, resume, idempotency,
    per-item isolation, reconciliation and the session-as-job-record contract
    are all unchanged. ``max_workers`` is configurable and defaults to ``1``
    (the exact pre-L10 single-dispatcher behavior).
    """

    def __init__(
        self,
        repository_factory: RepositoryFactory,
        storage: FileStorage,
        parsers: DocumentParsers,
        *,
        lease_stale_seconds: float = 30.0,
        max_workers: int = 1,
    ) -> None:
        self._repository_factory = repository_factory
        self._storage = storage
        self._parsers = parsers
        self._lease_stale_seconds = lease_stale_seconds
        self._max_workers = max(1, int(max_workers or 1))
        # Deterministic, unique worker identity (host + pid + process-unique
        # suffix): two managers can never collide, one manager is stable.
        self._owner = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._flags: dict[str, dict[str, bool]] = {}
        self._enqueued: set[str] = set()
        self._active_id: str | None = None
        # L10: the full set of concurrently-active sessions (for the pool).
        # ``_active_id`` is preserved as the backward-compatible representative.
        self._active_ids: set[str] = set()
        self._shutdown = False
        self._workers = [
            threading.Thread(
                target=self._drain_loop, name=f"intake-dispatcher-{i}", daemon=True
            )
            for i in range(self._max_workers)
        ]
        for worker in self._workers:
            worker.start()

    @property
    def owner_id(self) -> str:
        """This manager's lease identity (diagnostics + tests)."""

        return self._owner

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
            if session_id in self._enqueued or self._is_active(session_id):
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

    def _is_active(self, session_id: str) -> bool:
        """True when ``session_id`` is actively draining on any worker."""
        with self._lock:
            active_ids = getattr(self, "_active_ids", None)
            if active_ids is not None:
                return session_id in active_ids
            return self._active_id == session_id

    def is_active(self, session_id: str) -> bool:
        return self._is_active(session_id)

    def queued_count(self) -> int:
        with self._lock:
            return len(self._enqueued)

    def active_session(self) -> str | None:
        """A representative currently-active session (backward compatible)."""
        with self._lock:
            return self._active_id

    def active_session_ids(self) -> tuple[str, ...]:
        """All currently-active sessions (L10 pool diagnostics)."""
        with self._lock:
            active_ids = getattr(self, "_active_ids", None)
            if active_ids is None:
                return (self._active_id,) if self._active_id else ()
            return tuple(sorted(active_ids))

    @property
    def max_workers(self) -> int:
        """The configured bounded worker-pool size."""
        return self._max_workers

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

    # ----------------------------------------------------- durable lease
    def _lease_of(self, session: UniversalObject | None) -> dict | None:
        """Decode the lease record on the session (``None`` when none)."""

        if session is None:
            return None
        data = json_decode(session.metadata.get_value(KEY_LEASE), None)
        return data if isinstance(data, dict) else None

    def _lease_fresh(self, lease: dict) -> bool:
        """A lease is alive while its heartbeat is newer than the stale TTL."""

        try:
            heartbeat = dt.datetime.fromisoformat(str(lease.get("heartbeat_at") or ""))
        except ValueError:
            return False
        age = (dt.datetime.now(dt.UTC) - heartbeat).total_seconds()
        return age < self._lease_stale_seconds

    def acquire_session(self, repository: ObjectRepository, session: UniversalObject) -> bool:
        """Take the durable worker lease on the session.

        Deterministic protocol: a fresh foreign lease means *busy* (the
        other worker legitimately owns the drain — never duplicate it);
        write ours and **verify ownership after write** — a lost race is
        detected, not papered over. Stale/absent leases (crash orphans) are
        adopted with the prior acquired_at preserved for audit.
        """

        try:
            return self._acquire_on(repository, session)
        except OptimisticConcurrencyError:
            # R3 — a control write (pause/cancel) landed between the
            # dispatcher's load and this lease write. The row is
            # authoritative: re-load and re-apply the lease once; the
            # record is computed from the row, so the retry is honest.
            fresh = repository.get_by_id(ObjectId(str(session.id)))
            if fresh is None:
                return False
            return self._acquire_on(repository, fresh)

    def _acquire_on(self, repository: ObjectRepository, session: UniversalObject) -> bool:
        """Single lease-write attempt on a given session instance."""
        lease = self._lease_of(session)
        if (
            lease is not None
            and lease.get("owner") != self._owner
            and self._lease_fresh(lease)
        ):
            return False
        now = utcnow_iso()
        still_ours = lease is not None and lease.get("owner") == self._owner
        record = {
            "owner": self._owner,
            "acquired_at": lease.get("acquired_at") if still_ours else now,
            "heartbeat_at": now,
        }
        session.set_metadata(_lease_entry(record), actor=INTAKE_ACTOR)
        repository.save(session)
        fresh = repository.get_by_id(ObjectId(str(session.id)))
        verify = self._lease_of(fresh)
        return (
            verify is not None
            and verify.get("owner") == self._owner
            and verify.get("heartbeat_at") == now
        )

    def heartbeat_session(self, session: UniversalObject) -> None:
        """Refresh the lease heartbeat. The caller persists the row (the
        runner folds this into its per-item session save — zero extra I/O)."""

        lease = self._lease_of(session) or {}
        record = {
            "owner": self._owner,
            "acquired_at": lease.get("acquired_at") or utcnow_iso(),
            "heartbeat_at": utcnow_iso(),
        }
        session.set_metadata(_lease_entry(record), actor=INTAKE_ACTOR)

    def release_session(self, repository: ObjectRepository, session_id: str) -> None:
        """Drop our lease (only ours — never a foreign worker's)."""

        fresh = repository.get_by_id(ObjectId(session_id))
        lease = self._lease_of(fresh)
        if fresh is not None and lease is not None and lease.get("owner") == self._owner:
            fresh.set_metadata(_lease_entry(None), actor=INTAKE_ACTOR)
            repository.save(fresh)

    def _fail_after_crash(self, repository: ObjectRepository, session_id: str) -> None:
        """Best-effort FAILED write when a drain escapes unexpectedly.

        The runner persists its own failures (control aborts and systemic
        errors); this fires only when even those guards couldn't write — the
        classic case being a transient DB lock error that beat the failure
        persist itself. An honestly failed session beats a silently wedged
        one: the row becomes resumable *now* instead of stuck queued/running
        until a process restart lets ``reconcile_interrupted`` adopt it.

        Discipline: never clobbers a settled state (pause/cancel/complete
        that did land), never fights a live foreign worker (fresh lease),
        never resurrects a deleted session, and ignore-errors by contract —
        the lease TTL plus reconcile remain the backstop.
        """

        try:
            fresh = repository.get_by_id(ObjectId(session_id))
            if fresh is None:
                return  # deleted underneath the crash — rows are gone
            status = fresh.metadata.get_value(KEY_INTAKE_STATUS) or ""
            if status not in _TRANSIENT_STATUSES:
                return  # already settled honestly — leave it untouched
            lease = self._lease_of(fresh)
            if (
                lease is not None
                and lease.get("owner") != self._owner
                and self._lease_fresh(lease)
            ):
                return  # a live worker owns this session — never duplicate it
            stage = fresh.metadata.get_value(KEY_CURRENT_STAGE) or "session"
            message = "Worker crashed unexpectedly — resume to continue."
            fresh.set_metadata(
                MetadataEntry(
                    KEY_ERROR,
                    json_encode({"stage": stage, "message": message}),
                    MetadataLayer.L1_SYSTEM,
                    Provenance.SYSTEM,
                ),
                actor=INTAKE_ACTOR,
            )
            fresh.set_metadata(
                MetadataEntry(
                    KEY_ENDED_AT, utcnow_iso(), MetadataLayer.L1_SYSTEM, Provenance.SYSTEM
                ),
                actor=INTAKE_ACTOR,
            )
            fresh.set_metadata(
                MetadataEntry(
                    KEY_INTAKE_STATUS,
                    IntakeSessionStatus.FAILED.value,
                    MetadataLayer.L1_SYSTEM,
                    Provenance.SYSTEM,
                ),
                actor=INTAKE_ACTOR,
            )
            repository.save(fresh)
        except Exception:  # noqa: BLE001 — best effort by contract; a stale
            pass  # lease self-expires and reconcile is the restart backstop.

    def _drain_loop(self) -> None:
        while True:
            session_id = self._queue.get()
            acquired = False
            try:
                if session_id is None:  # shutdown sentinel
                    return
                with self._lock:
                    self._enqueued.discard(session_id)
                repository, cleanup = self._repository_factory()
                try:
                    session = repository.get_by_id(ObjectId(session_id))
                    if session is None:
                        continue  # deleted before the dispatcher picked it up
                    if session.metadata.get_value(KEY_INTAKE_STATUS) in (
                        IntakeSessionStatus.CANCELLED.value,
                        IntakeSessionStatus.COMPLETED.value,
                    ):
                        continue  # terminal between enqueue and pickup
                    acquired = self.acquire_session(repository, session)
                    if not acquired:
                        continue  # a live worker owns it — no duplicate drain
                    with self._lock:
                        # Claim only proven ownership: before this line the
                        # manager must never report the session as active.
                        self._active_id = session_id
                        active_ids = getattr(self, "_active_ids", None)
                        if active_ids is not None:
                            active_ids.add(session_id)
                    runner = IntakeRunner(
                        repository,
                        self._storage,
                        session_id,
                        self._control_probe(session_id),
                        self._parsers,
                        on_item=self.heartbeat_session,
                    )
                    runner.run()
                except Exception:  # noqa: BLE001 — the dispatcher must never
                    # die with a job — but it never swallows a crash silently.
                    _log.exception("Intake drain crashed for %s", session_id)
                    self._fail_after_crash(repository, session_id)
                finally:
                    try:
                        if acquired:
                            self.release_session(repository, session_id)
                    except Exception:  # noqa: BLE001 — release is best-effort;
                        pass  # a stale lease expires on its own TTL.
                    cleanup()
            finally:
                with self._lock:
                    active_ids = getattr(self, "_active_ids", None)
                    if active_ids is not None:
                        active_ids.discard(session_id)
                    if self._active_id == session_id:
                        self._active_id = (
                            next(iter(active_ids)) if active_ids else None
                        )
                self._queue.task_done()

    # --------------------------------------------------------- reconcile
    def reconcile_interrupted(self) -> int:
        """Mark sessions left queued/running by a *dead* process as FAILED
        (resumable — the resume endpoint continues them). Returns the count.

        M2.3: a session carrying a **fresh** lease belongs to a live worker
        (possibly this very manager mid-drain) and is skipped — reconcile
        must never fight a healthy drain. Stale or absent leases are crash
        orphans and adoptable.
        """

        repository, cleanup = self._repository_factory()
        try:
            sessions = repository.find(object_type=ObjectType.INTAKE_SESSION)
            count = 0
            for session in sessions:
                status = session.metadata.get_value(KEY_INTAKE_STATUS) or ""
                if status not in _TRANSIENT_STATUSES:
                    continue
                lease = self._lease_of(session)
                if lease is not None and self._lease_fresh(lease):
                    continue  # a live worker owns this session
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
                # The orphan lease is spent — drop it with the same write.
                session.set_metadata(_lease_entry(None), actor=INTAKE_ACTOR)
                try:
                    repository.save(session)
                except OptimisticConcurrencyError:
                    # R3 — the row moved under reconcile (e.g. a control
                    # write landed while we were marking it failed). Skip:
                    # the row is authoritative and the next reconcile pass
                    # re-evaluates it.
                    continue
                count += 1
            return count
        finally:
            cleanup()

    # ---------------------------------------------------------- shutdown
    def shutdown(self, timeout: float = 10.0) -> None:
        """Stop all dispatcher threads (tests + app shutdown). In-flight drains
        persist their last checkpoint first; queued sessions stay resumable."""

        with self._lock:
            self._shutdown = True
        # One sentinel per worker so every dispatcher thread exits.
        for _ in range(self._max_workers):
            self._queue.put(None)
        for worker in self._workers:
            worker.join(timeout=timeout)
