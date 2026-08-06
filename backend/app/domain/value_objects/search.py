"""Search projection value type (Sprint-5 M1 — Global Search Foundation).

``SearchDocument`` is the deterministic projection of ONE Object's searchable
state. It is a pure value object over JSON primitives, exactly like the
snapshot types: it never queries, never persists, and never decides. The
fields are the roadmap-approved searchable surface:

- ``object_id`` / ``object_type`` / ``title`` — the object's identity and
  approved scalar fields;
- ``metadata_text`` — the deterministic text form of the object's metadata
  (``key: value`` lines, sorted by key);
- ``version`` — the object version this document reflects, so index writes
  are version-aware (a stale projection can never overwrite a newer one).

The document is derived ONLY from an ``ObjectSnapshot`` via the frozen
mapping (``app.infrastructure.persistence.search_mapping``); the search
index is a derived projection and never the source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchDocument:
    object_id: str  # ObjectId value
    object_type: str  # ObjectType value
    title: str
    metadata_text: str
    version: int
