"""Health probe route (no auth, no business logic)."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "academicos-api",
        "version": settings.version,
        "environment": settings.environment,
    }
