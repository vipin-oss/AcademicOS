"""L3 decision record + audit DTO (ADR-032).

A durable, attributable record of one human decision on a claim or CDM block.
``decision_id`` is the idempotency key. This is application-layer (stdlib only).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    subject_id: str
    decision: str
    reviewer: str
    previous_status: str
    resulting_status: str
    notes: str = ""
    acl_scope: str | None = None
    eval_run_id: str | None = None
    created_at: str = field(default_factory=_utcnow_iso)


def new_decision_id() -> str:
    return f"decision:{uuid.uuid4().hex[:16]}"
