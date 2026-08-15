"""L10 architecture guardrails (ADR-048/049).

Pins that L10:
- reuses stdlib threads + queue only (no Kafka/Celery/Redis/Temporal/microservices);
- adds no new capability ID (frozen 18-capability registry unchanged);
- does not modify frozen L0-L9 production or evaluation architecture;
- does not add a migration;
- preserves the intake job semantics (idempotency, leases, per-item isolation,
  retry, resume, reconcile);
- defaults max_workers=1 for backward compatibility.
"""

from __future__ import annotations

import inspect
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ARCH = REPO / "docs" / "architecture"


def test_l10_adrs_present():
    for name in (
        "ADR-048-l10-ingestion-scale-worker-pool",
        "ADR-049-l10-evaluation-gate",
    ):
        assert (ARCH / "adr" / f"{name}.md").exists(), f"missing {name}"


def test_levels_marks_l9_done_l10_in_progress():
    text = (ARCH / "LEVELS.md").read_text(encoding="utf-8")
    assert "L9" in text and "done" in text
    assert "L10" in text and "in_progress" in text
    # L11+ must not have started
    assert "L11" in text and "not_started" in text


def test_l10_no_new_capability_ids():
    from app.application.capabilities.registry import FROZEN_CAPABILITY_IDS

    assert len(FROZEN_CAPABILITY_IDS) == 18


def test_l10_reuses_stdlib_threads_queue_only():
    src = (REPO / "backend" / "app" / "application" / "intake" / "jobs.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("kafka", "celery", "redis", "temporal", "sqlalchemy.Queue", "pika"):
        assert forbidden not in src.lower(), f"L10 must not use {forbidden}"
    assert "threading" in src and "queue.Queue" in src


def test_l10_no_new_migration():
    migrations = REPO / "backend" / "alembic" / "versions"
    names = [p.name for p in migrations.glob("*.py")]
    # Migration head is 0016 (typed claims, V3 M5). L10 itself adds none.
    assert not any("0017" in n for n in names), names


def test_l10_defaults_max_workers_one():
    src = (REPO / "backend" / "app" / "application" / "intake" / "jobs.py").read_text(
        encoding="utf-8"
    )
    assert "max_workers: int = 1" in src


def test_l10_does_not_touch_frozen_production():
    l10_new = {
        "backend/app/application/use_cases/intake/dead_letter.py",
        "backend/app/tests/eval/test_l10_eval_gate.py",
        "backend/app/tests/architecture/test_l10_guardrails.py",
        "backend/app/tests/integration/test_intake_worker_pool.py",
    }
    frozen = {
        "backend/app/application/capabilities/registry.py",
        "backend/app/application/services/planner.py",
        "backend/app/application/services/fast_path.py",
        "backend/app/application/services/tool_executor.py",
        "backend/app/application/services/claim_evidence.py",
        "backend/app/application/services/persistent_memory.py",
        "backend/app/application/services/cross_domain.py",
        "backend/app/application/services/assistant_eval.py",
    }
    assert l10_new.isdisjoint(frozen)
