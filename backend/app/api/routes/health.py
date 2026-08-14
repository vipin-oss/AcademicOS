"""Health / readiness routes (no auth, no business logic).

Two distinct questions, two endpoints (V3 M1):

- ``GET /health``  — *is the process alive?* Cheap, dependency-free, unchanged
  from R1 so existing probes and scripts keep working.
- ``GET /health/ready`` — *can this deployment actually serve?* Runs the
  bounded readiness probes (database + Alembic revision, outbox backlog,
  Qdrant reachability, AI providers and model residency).

The readiness endpoint never raises: a subsystem that cannot be determined is
reported as ``error``/``degraded`` with a short detail. The HTTP status is 200
when serving is possible and 503 only when a hard dependency is down, so an
orchestrator can act on it while an operator still gets the full picture.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.ai import get_ai_core
from app.application.ai.core import AiCore
from app.core.config import settings
from app.infrastructure.db.readiness import (
    STATUS_ERROR,
    aggregate_status,
    ai_probe,
    database_probe,
    outbox_probe,
    vector_probe,
)
from app.infrastructure.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness — unchanged R1 contract."""
    return {
        "status": "ok",
        "service": "academicos-api",
        "version": settings.version,
        "environment": settings.environment,
    }


@router.get("/health/ready")
def readiness(
    response: Response,
    db: Session = Depends(get_db),
    ai_core: AiCore = Depends(get_ai_core),
) -> dict:
    """Readiness — the operator-facing truth (V3 M1).

    This route is the composition root for the probes: it resolves the AI Core
    and injects it, so neither the application nor the infrastructure layer
    reaches into ``app.api`` (architecture guardrails).
    """
    probes = [
        database_probe(db),
        outbox_probe(db),
        vector_probe(),
        ai_probe(ai_core),
    ]
    overall = aggregate_status(probes)
    if overall == STATUS_ERROR:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": overall,
        "service": "academicos-api",
        "version": settings.version,
        "environment": settings.environment,
        "checks": {probe.name: probe.to_dict() for probe in probes},
    }
