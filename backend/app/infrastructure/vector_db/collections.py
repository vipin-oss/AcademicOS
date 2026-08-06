"""Versioned vector collection management (Sprint-5 M2 — design gate 17).

Owns the Qdrant collection lifecycle: an immutable, versioned base
collection (``search_objects_v{n}``) plus a stable alias
(``search_objects_active``) that all reads and writes go through. When the
embedding model changes, a NEW base collection is built and the alias is
re-pointed atomically (AI doc A2.5 dual-index alias swap) — the policy is
documented in ``docs/search_collection_policy.md``.

Parameters follow the AI doc A3.3 table (HNSW M=32 / ef_construct=256,
COSINE distance); ``ef_search`` is a search-time knob and is documented in
the policy rather than passed per-request, for local-mode parity.
"""
from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models

# The stable write/query target — never changes across embedding versions.
SEARCH_COLLECTION_ALIAS = "search_objects_active"
# Payload marker distinguishing the document-summary role (AI doc A3.2).
VECTOR_ROLE_DOC = "doc"
_HNSW_M = 32
_HNSW_EF_CONSTRUCT = 256


def collection_name_for_version(version: int) -> str:
    """The immutable base collection for an embedding version."""
    return f"search_objects_v{version}"


class VectorCollectionManager:
    """Idempotent collection + alias provisioning for one embedding version."""

    def __init__(self, client: QdrantClient, dimensions: int, *, version: int = 1) -> None:
        self._client = client
        self._dimensions = dimensions
        self._version = version

    def ensure(self) -> str:
        """Create the versioned collection and alias if missing; returns the
        active collection name (the alias). Safe to call on every request."""
        name = collection_name_for_version(self._version)
        if not self._client.collection_exists(name):
            self._client.create_collection(
                name,
                vectors_config=models.VectorParams(
                    size=self._dimensions,
                    distance=models.Distance.COSINE,
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=_HNSW_M,
                    ef_construct=_HNSW_EF_CONSTRUCT,
                ),
            )
        alias_names = {
            alias.alias_name
            for alias in self._client.get_collection_aliases(name).aliases
        }
        if SEARCH_COLLECTION_ALIAS not in alias_names:
            self._client.update_collection_aliases(
                change_aliases_operations=[
                    models.CreateAliasOperation(
                        create_alias=models.CreateAlias(
                            collection_name=name,
                            alias_name=SEARCH_COLLECTION_ALIAS,
                        )
                    )
                ]
            )
        return SEARCH_COLLECTION_ALIAS
