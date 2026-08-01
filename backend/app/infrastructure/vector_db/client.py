"""Qdrant vector-store client factory.

Infrastructure layer: the concrete vector adapter. Returns a configured
QdrantClient. Collection management lives behind application ports later.
"""
from __future__ import annotations

from qdrant_client import QdrantClient

from app.core.config import settings


def get_qdrant_client() -> QdrantClient:
    api_key = settings.qdrant_api_key or None
    return QdrantClient(url=settings.qdrant_url, api_key=api_key)
