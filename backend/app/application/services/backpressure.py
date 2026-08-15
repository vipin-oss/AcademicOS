"""Backpressure limiter for the durable job worker (V3 M10, ADR-057).

Bounds concurrent work so the worker can never overwhelm the system: a global
concurrency cap, a per-user quota, and a per-type concurrency cap. Limits are
config-driven; the worker consults the limiter before claiming each job.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BackpressureLimiter:
    global_limit: int = 10
    per_user_limit: int = 5
    per_type_limit: int = 5

    _running: set[str] = field(default_factory=set)
    _by_user: dict[str, int] = field(default_factory=dict)
    _by_type: dict[str, int] = field(default_factory=dict)

    def allow(self, *, job_id: str, job_type: str, owner_user_id: str) -> bool:
        """Whether a job may start under the current limits."""
        if len(self._running) >= self.global_limit:
            return False
        if self._by_user.get(owner_user_id, 0) >= self.per_user_limit:
            return False
        if self._by_type.get(job_type, 0) >= self.per_type_limit:
            return False
        return True

    def start(self, *, job_id: str, job_type: str, owner_user_id: str) -> None:
        self._running.add(job_id)
        self._by_user[owner_user_id] = self._by_user.get(owner_user_id, 0) + 1
        self._by_type[job_type] = self._by_type.get(job_type, 0) + 1

    def finish(self, *, job_id: str, job_type: str, owner_user_id: str) -> None:
        self._running.discard(job_id)
        self._by_user[owner_user_id] = max(0, self._by_user.get(owner_user_id, 1) - 1)
        self._by_type[job_type] = max(0, self._by_type.get(job_type, 1) - 1)

    def running(self) -> int:
        return len(self._running)


__all__ = ["BackpressureLimiter"]
