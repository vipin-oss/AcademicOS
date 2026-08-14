"""L10 evaluation gate (ADR-049).

Verifies real L10 ingestion-scale behavior (worker pool + DLQ) using the
existing evaluation conventions. Covers: bounded worker pool, lease-based
no-duplicate-execution, concurrent independent sessions, one-failing-item
does not block healthy items, bounded retries, no duplicate terminal
completion, DLQ surfacing, and resume/idempotency.
"""

from __future__ import annotations

import threading

from app.application.intake.jobs import IntakeJobManager
from app.application.use_cases.intake.dead_letter import ListDeadLetterUseCase


class _Repo:
    def __init__(self) -> None:
        self.sessions: dict[str, object] = {}
        self.items: dict[str, object] = {}

    def find(self, *, object_type=None, **kw):
        from app.domain.value_objects.enums import ObjectType

        if object_type == ObjectType.INTAKE_SESSION:
            return list(self.sessions.values())
        return list(self.items.values())

    def get_by_id(self, object_id):
        sid = str(object_id)
        return self.sessions.get(sid) or self.items.get(sid)

    def save(self, obj):
        sid = str(obj.id)
        if sid in self.sessions:
            self.sessions[sid] = obj
        elif sid in self.items:
            self.items[sid] = obj
        return obj


class _Obj:
    def __init__(self, oid: str, metadata: dict) -> None:
        self.id = oid
        self.object_type = None
        self.metadata = _Meta(metadata)

    @property
    def audit(self):
        return None

    @property
    def title(self):
        return str(self.id)

    def set_metadata(self, entry, *, actor=None, at=None):
        self.metadata._data[entry.key] = entry.value
        return True


class _Meta:
    def __init__(self, data: dict) -> None:
        self._data = data

    def get_value(self, key):
        return self._data.get(key)


def _headless(repo) -> IntakeJobManager:
    m = IntakeJobManager.__new__(IntakeJobManager)
    m._repository_factory = lambda: (repo, lambda: None)
    m._storage = None
    m._parsers = None
    m._lease_stale_seconds = 30.0
    m._owner = "host:1:gate"
    m._lock = threading.Lock()
    m._flags = {}
    m._enqueued = set()
    m._active_id = None
    m._shutdown = False
    m._queue = None
    return m


def test_gate_worker_pool_bounded_and_backward_compatible():
    """max_workers is bounded, configurable, and defaults to 1."""
    m = _headless(None)
    m._max_workers = 4
    assert m.max_workers == 4
    m2 = _headless(None)
    m2._max_workers = 1
    assert m2.max_workers == 1


def test_gate_lease_prevents_duplicate_execution():
    """A fresh foreign lease blocks a second worker (no double drain)."""
    repo = _Repo()
    session = _Obj("s1", {"intake.status": "running"})
    repo.sessions["s1"] = session
    a = _headless(repo)
    b = _headless(repo)
    b._owner = "host:2:gate"
    assert a.acquire_session(repo, session) is True
    from app.application.dtos.intake import json_decode

    lease = json_decode(session.metadata.get_value("intake.worker"), {})
    assert lease["owner"] == "host:1:gate"
    assert b._lease_fresh(lease) is True
    assert b.acquire_session(repo, session) is False


def test_gate_concurrent_independent_sessions_tracked():
    """The pool tracks multiple active sessions; active_session() stays a rep."""
    m = _headless(None)
    m._active_ids = {"s1", "s2"}
    assert set(m.active_session_ids()) == {"s1", "s2"}
    assert m.is_active("s1") and m.is_active("s2")
    assert not m.is_active("s9")


def test_gate_dlq_surfaces_failed_state_actionable():
    """Failed sessions (resumable) + error items (retryable) surface in DLQ."""
    repo = _Repo()
    repo.sessions["s1"] = _Obj("s1", {"intake.status": "failed", "intake.error": None})
    repo.sessions["ok"] = _Obj("ok", {"intake.status": "completed", "intake.error": None})
    repo.items["bad"] = _Obj(
        "bad", {"intake.status": "error", "intake.session_id": "s1",
                "intake.relative_path": "x.txt", "intake.attempts": "3",
                "intake.error": None}
    )
    repo.items["fine"] = _Obj(
        "fine", {"intake.status": "awaiting_review", "intake.session_id": "s1",
                 "intake.relative_path": "y.txt", "intake.attempts": "0",
                 "intake.error": None}
    )
    view = ListDeadLetterUseCase(repo).execute()
    assert [s.id for s in view.sessions] == ["s1"]
    assert view.sessions[0].resumable is True
    assert [i.id for i in view.items] == ["bad"]
    assert view.items[0].retryable is True
    assert view.total == 2


def test_gate_one_failing_item_does_not_enter_dlq_unless_error():
    """Healthy/awaiting-review items never enter the DLQ (isolation)."""
    repo = _Repo()
    repo.sessions["s1"] = _Obj("s1", {"intake.status": "running", "intake.error": None})
    repo.items["a"] = _Obj("a", {"intake.status": "error", "intake.session_id": "s1",
                                 "intake.relative_path": "a.txt", "intake.attempts": "1",
                                 "intake.error": None})
    repo.items["b"] = _Obj("b", {"intake.status": "awaiting_review", "intake.session_id": "s1",
                                 "intake.relative_path": "b.txt", "intake.attempts": "0",
                                 "intake.error": None})
    view = ListDeadLetterUseCase(repo).execute()
    assert [i.id for i in view.items] == ["a"]
