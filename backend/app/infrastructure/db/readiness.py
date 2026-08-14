"""Readiness probes (V3 M1 — Instrumentation & Truthful Baseline).

Answers one question honestly: *is this deployment actually able to serve?*

Each probe is independent, bounded, and non-raising — a probe that cannot
determine its subsystem reports ``status="error"`` with a short detail rather
than throwing, because a health endpoint that 500s tells an operator nothing.

Probes provided (V3 M1 scope, no more):

- ``database_probe``      — connectivity + Alembic revision (schema-vs-code drift)
- ``outbox_probe``        — pending (undelivered) event backlog
- ``vector_probe``        — Qdrant reachability
- ``ai_probe``            — provider catalogue + whether a model is resident

Deliberately NOT here: metrics backends, alerting, retries, background
polling. M1 makes truth *visible*; acting on it belongs to later milestones.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session

#: Probe status vocabulary — deliberately tiny and unambiguous.
STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_ERROR = "error"
STATUS_DISABLED = "disabled"


@dataclass(frozen=True)
class ProbeResult:
    """One subsystem's readiness verdict."""

    name: str
    status: str
    detail: str = ""
    latency_ms: float = 0.0
    facts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        payload: dict = {
            "status": self.status,
            "latency_ms": round(self.latency_ms, 3),
        }
        if self.detail:
            payload["detail"] = self.detail
        payload.update(self.facts)
        return payload


class _Timer:
    """Monotonic stopwatch for probe latency."""

    def __enter__(self) -> _Timer:
        self._start = time.perf_counter()
        self.elapsed_ms = 0.0
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0


# --------------------------------------------------------------------- database
def database_probe(session: Session) -> ProbeResult:
    """Connectivity plus the applied Alembic revision.

    The revision matters: V3 records schema-vs-code drift as a first-class
    fact (the blueprint's own assumption list flagged the database trailing
    the code head). Reporting it beats discovering it during a migration.
    """
    with _Timer() as timer:
        try:
            session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 — a probe reports, never raises
            return ProbeResult(
                name="database",
                status=STATUS_ERROR,
                detail=f"{type(exc).__name__}: {exc}",
                latency_ms=timer.elapsed_ms if hasattr(timer, "elapsed_ms") else 0.0,
            )
    revision = _alembic_revision(session)
    return ProbeResult(
        name="database",
        status=STATUS_OK,
        latency_ms=timer.elapsed_ms,
        facts={"alembic_revision": revision},
    )


def _alembic_revision(session: Session) -> str | None:
    """The applied migration revision, or ``None`` when unavailable."""
    try:
        row = session.execute(text("SELECT version_num FROM alembic_version")).first()
    except Exception:  # noqa: BLE001 — table absent on a fresh/SQLite dev db
        return None
    return str(row[0]) if row else None


# ----------------------------------------------------------------------- outbox
def outbox_probe(session: Session) -> ProbeResult:
    """Undelivered outbox backlog — the projection-lag signal.

    A growing backlog means search/vector projections are falling behind the
    authoritative store. V3 removes read-time drain (M8), so this number is
    how an operator sees the relay's health.
    """
    with _Timer() as timer:
        try:
            row = session.execute(
                text(
                    "SELECT COUNT(*) FROM outbox_events WHERE delivered_at IS NULL"
                )
            ).first()
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(
                name="outbox",
                status=STATUS_ERROR,
                detail=f"{type(exc).__name__}: {exc}",
            )
    pending = int(row[0]) if row else 0
    return ProbeResult(
        name="outbox",
        status=STATUS_OK,
        latency_ms=timer.elapsed_ms,
        facts={"pending": pending},
    )


# ----------------------------------------------------------------------- vector
def vector_probe(client_factory=None) -> ProbeResult:
    """Qdrant reachability. Absent/unreachable is DEGRADED, never fatal:
    V3 §Retrieval requires search to fall back to the lexical leg."""
    with _Timer() as timer:
        try:
            if client_factory is None:
                from app.infrastructure.vector_db.client import get_qdrant_client

                client_factory = get_qdrant_client
            client = client_factory()
            collections = client.get_collections()
            count = len(getattr(collections, "collections", []) or [])
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(
                name="vector",
                status=STATUS_DEGRADED,
                detail=f"unreachable ({type(exc).__name__})",
                facts={"fallback": "lexical"},
            )
    return ProbeResult(
        name="vector",
        status=STATUS_OK,
        latency_ms=timer.elapsed_ms,
        facts={"collections": count},
    )


# --------------------------------------------------------------------------- ai
def ai_probe(ai_core) -> ProbeResult:
    """Provider catalogue plus model residency.

    ``model_resident`` is the V3 M1 fact that matters for speed: a cold model
    means the first user request pays the load cost. It is set by
    :func:`app.application.ai.warmup.prewarm` and reported here.

    ``ai_core`` is injected by the caller (the health route is the composition
    root). Infrastructure must not import the api layer — enforced by
    ``test_application_guardrails``.
    """
    from app.application.ai.warmup import warmup_state

    with _Timer() as timer:
        try:
            if ai_core is None:
                return ProbeResult(
                    name="ai",
                    status=STATUS_DISABLED,
                    detail="AI Core not supplied",
                    facts={"model_resident": False},
                )
            provider_ids = list(ai_core.provider_ids)
            summary = ai_core.health_summary()
            executable = bool(getattr(summary, "executable", False))
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(
                name="ai",
                status=STATUS_ERROR,
                detail=f"{type(exc).__name__}: {exc}",
            )

    state = warmup_state()
    facts: dict = {
        "providers": provider_ids,
        "executable": executable,
        "model_resident": state.resident,
    }
    if state.model:
        facts["model"] = state.model
    if state.warmup_ms is not None:
        facts["warmup_ms"] = round(state.warmup_ms, 3)
    if state.detail:
        facts["detail"] = state.detail

    if not provider_ids:
        status = STATUS_DISABLED
    elif executable and state.resident:
        status = STATUS_OK
    else:
        status = STATUS_DEGRADED
    return ProbeResult(name="ai", status=status, latency_ms=timer.elapsed_ms, facts=facts)


# ------------------------------------------------------------------- aggregate
def aggregate_status(probes: list[ProbeResult]) -> str:
    """Worst-of aggregation, ignoring intentionally disabled subsystems."""
    if any(p.status == STATUS_ERROR for p in probes):
        return STATUS_ERROR
    if any(p.status == STATUS_DEGRADED for p in probes):
        return STATUS_DEGRADED
    return STATUS_OK


__all__ = [
    "STATUS_DEGRADED",
    "STATUS_DISABLED",
    "STATUS_ERROR",
    "STATUS_OK",
    "ProbeResult",
    "ai_probe",
    "aggregate_status",
    "database_probe",
    "outbox_probe",
    "vector_probe",
]
