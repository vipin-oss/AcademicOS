"""Deterministic T0 embedder (Sprint-5 M2 — semantic search leg).

The hashing trick over normalized tokens: each token hashes to a signed
dimension (sha256 — stable across processes), the vector is the sum of
token contributions, L2-normalized. Same text -> same vector, always.
In-process, no model, no network (AI doc A4.1 T0 tier).

This is the CI-safe default embedder; a T2 encoder replaces it behind the
same port without touching the pipeline.
"""
from __future__ import annotations

import hashlib
import math
import re

from app.application.ports.embedder import Embedder

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingEmbedder(Embedder):
    def __init__(self, dimensions: int = 256) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive.")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for token in _TOKEN_RE.findall((text or "").lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self._dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]
