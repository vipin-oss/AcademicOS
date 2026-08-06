"""Deterministic snapshot -> search-document mapping (Sprint-5 M1).

The single mapping between the frozen snapshot representation and the
search projection. Same snapshot in -> same document out, always: metadata
entries are canonicalised by key order, and no external state (time,
identity, randomness) enters the mapping. Search documents are therefore
reproducible entirely from version snapshots — the rebuild path and the
outbox path produce byte-identical projections.

The mapping indexes ONLY the roadmap-approved searchable fields already
present in snapshots: ``object_type``, ``title``, and the metadata text.
No new serialization format exists here — the snapshot stays the single
source.
"""
from __future__ import annotations

from app.domain.value_objects.search import SearchDocument
from app.infrastructure.persistence.snapshots import (
    MetadataSnapshot,
    ObjectSnapshot,
)


def to_search_document(snapshot: ObjectSnapshot) -> SearchDocument:
    """Project one immutable snapshot into its search document."""
    return SearchDocument(
        object_id=snapshot.id,
        object_type=snapshot.object_type,
        title=snapshot.title,
        metadata_text=_metadata_text(snapshot.metadata),
        version=snapshot.version,
    )


def _metadata_text(entries: tuple[MetadataSnapshot, ...]) -> str:
    """Deterministic ``key: value`` text form of the metadata entries.

    Sorted by key so the text depends only on the entry SET, never on
    insertion order — the same snapshot always maps to the same text.
    """
    return "\n".join(
        f"{entry.key}: {entry.value}" for entry in sorted(entries, key=lambda m: m.key)
    )
