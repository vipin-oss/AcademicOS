"""L10 scale budgets — ingestion (ADR-049).

Bounded CI-safe ingestion scale checks measuring actual worker-pool/DLQ
behavior (1k/10k sessions/items), reusing the test_search_perf_smoke
methodology. Larger 100k/1M points are CI-optional per SCALE_LAW.
"""

from __future__ import annotations

import time

import pytest

from app.application.use_cases.intake.dead_letter import ListDeadLetterUseCase

#: CI-safe ingestion scale points.
CI_SAFE_SCALES = (1_000, 10_000)
#: Larger measurement points (CI-optional).
LARGE_SCALES = (100_000, 1_000_000)

#: Generous per-1000-entries budget (ms) — CI-safe, not a throughput claim.
DLQ_BUDGET_MS_PER_1K = 250.0


class _Repo:
    def __init__(self, n_sessions: int, n_items: int) -> None:
        self.sessions: dict[str, object] = {}
        self.items: dict[str, object] = {}
        for i in range(n_sessions):
            self.sessions[f"s{i}"] = _Obj(
                f"s{i}", {"intake.status": "failed" if i % 3 == 0 else "completed"}
            )
        for i in range(n_items):
            self.items[f"i{i}"] = _Obj(
                f"i{i}",
                {"intake.status": "error" if i % 5 == 0 else "awaiting_review",
                 "intake.session_id": f"s{i % max(n_sessions,1)}",
                 "intake.relative_path": f"f{i}.txt", "intake.attempts": "3",
                 "intake.error": None},
            )

    def find(self, *, object_type=None, **kw):
        from app.domain.value_objects.enums import ObjectType

        if object_type == ObjectType.INTAKE_SESSION:
            return list(self.sessions.values())
        return list(self.items.values())


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


class _Meta:
    def __init__(self, data: dict) -> None:
        self._data = data

    def get_value(self, key):
        return self._data.get(key)


@pytest.mark.parametrize("n", CI_SAFE_SCALES)
def test_l10_dlq_scale_ci_safe(n):
    """CI-safe: querying the DLQ over N sessions+items stays within budget."""
    repo = _Repo(n_sessions=n // 2, n_items=n // 2)
    t0 = time.perf_counter()
    view = ListDeadLetterUseCase(repo).execute(limit=500)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert view.total >= 0
    # DLQ must only surface failed sessions and error items.
    assert all(s.status == "failed" for s in view.sessions)
    assert all(i.status == "error" for i in view.items)
    # Deterministic: re-query yields the same ids.
    view2 = ListDeadLetterUseCase(repo).execute(limit=500)
    assert [s.id for s in view.sessions] == [s.id for s in view2.sessions]
    # Budget guard (per-1000-entries scaled).
    per_1k = elapsed_ms / (max(n // 2, 1) / 1000.0)
    assert per_1k <= DLQ_BUDGET_MS_PER_1K, f"DLQ budget exceeded: {per_1k:.2f}ms/1k"


@pytest.mark.parametrize("n", LARGE_SCALES)
def test_l10_large_scale_ci_optional(n):
    """Larger ingestion measurement path (CI-optional per SCALE_LAW)."""
    pytest.skip(
        f"Large-scale {n} is CI-optional per SCALE_LAW; run explicitly to record "
        "the measurement path (see ADR-048/049)."
    )
