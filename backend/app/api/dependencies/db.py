"""Database dependency adapter for the API layer.

Re-exports the infrastructure session dependency so API routers depend on a
stable path rather than reaching into infrastructure directly.
"""
from __future__ import annotations

from app.infrastructure.db.session import get_db

__all__ = ["get_db"]
