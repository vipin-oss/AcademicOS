"""Application port: text embedder (Sprint-5 M2 — semantic search leg).

The single seam between the semantic pipeline and any embedding model. The
port is deterministic by contract: the same text always produces the same
vector, so indexing, querying and rebuilding are reproducible and testable
without a model server.

Frozen reference (AI doc): models are swappable behind an internal
abstraction (P8); the T0 deterministic tier runs in-process with no model
(A4.1). A T2 encoder (E5/BGE-M3 class, A4.2) plugs in later behind this
same port — nothing in the pipeline changes.
"""
from __future__ import annotations

import abc


class Embedder(abc.ABC):
    @abc.abstractmethod
    def embed(self, text: str) -> list[float]:
        """The deterministic dense vector for ``text`` (L2-normalized)."""

    @property
    @abc.abstractmethod
    def dimensions(self) -> int:
        """Vector dimensionality — the collection schema contract."""
