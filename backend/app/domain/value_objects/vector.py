"""Semantic projection value type (Sprint-5 M2 — Global Search, semantic leg).

``VectorDocument`` is the deterministic semantic projection of ONE object's
searchable state: the same fields as the lexical ``SearchDocument`` plus the
embedding of its search text. Pure value object over JSON primitives — it
never queries, never persists, and never decides.

Like the lexical projection, it is derived (the object and its version
snapshots remain authoritative) and version-aware (``version`` guards
against stale overwrites).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VectorDocument:
    object_id: str  # ObjectId value
    object_type: str  # ObjectType value
    title: str
    metadata_text: str
    version: int
    vector: tuple[float, ...]  # the embedder's deterministic embedding
