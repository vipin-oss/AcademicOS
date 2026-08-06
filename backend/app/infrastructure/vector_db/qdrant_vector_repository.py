"""Qdrant adapter for the VectorRepository port (Sprint-5 M2).

Implements the same contract as ``FakeVectorRepository`` (the reference
implementation) against a Qdrant server: version-aware upserts (stale
never overwrites — checked via retrieve before write), idempotent delete,
cosine nearest-neighbour search with deterministic ``object_id`` tie-breaks
(post-sorted by ``(-score, object_id)``), and ``clear`` for the rebuild
path.

Point ids are deterministic UUID5 values derived from the object id: the
local Qdrant emulator (CI) requires UUID ids, and the real server accepts
them — the authoritative ``object_id`` always lives in the payload.
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.domain.repositories.vector_repository import VectorRepository
from app.domain.value_objects.vector import VectorDocument
from app.infrastructure.vector_db.collections import VECTOR_ROLE_DOC


class QdrantVectorRepository(VectorRepository):
    def __init__(self, client: QdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    @staticmethod
    def _point_id(object_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, object_id))

    def upsert(self, document: VectorDocument) -> None:
        point_id = self._point_id(document.object_id)
        existing = self._client.retrieve(
            self._collection, ids=[point_id], with_payload=True
        )
        if existing and int(existing[0].payload.get("version", 0)) > document.version:
            return  # version guard: a stale projection never overwrites
        self._client.upsert(
            self._collection,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=list(document.vector),
                    payload={
                        "object_id": document.object_id,
                        "object_type": document.object_type,
                        "title": document.title,
                        "metadata_text": document.metadata_text,
                        "version": document.version,
                        "vector_role": VECTOR_ROLE_DOC,
                    },
                )
            ],
        )

    def delete(self, object_id: str) -> None:
        self._client.delete(
            self._collection, points_selector=[self._point_id(object_id)]
        )

    def search(
        self, vector: Sequence[float], *, limit: int = 50
    ) -> list[VectorDocument]:
        hits = self._client.search(
            self._collection,
            query_vector=list(vector),
            limit=limit,
            with_payload=True,
            with_vectors=True,
        )
        # Deterministic ordering identical to the reference implementation:
        # similarity desc, object_id asc.
        hits.sort(key=lambda hit: (-hit.score, hit.payload["object_id"]))
        return [
            VectorDocument(
                object_id=hit.payload["object_id"],
                object_type=hit.payload["object_type"],
                title=hit.payload["title"],
                metadata_text=hit.payload.get("metadata_text", ""),
                version=int(hit.payload["version"]),
                vector=tuple(hit.vector),
            )
            for hit in hits
        ]

    def clear(self) -> None:
        self._client.delete(
            self._collection,
            points_selector=models.FilterSelector(filter=models.Filter()),
        )
