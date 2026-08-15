"""Application port: token-revocation denylist (V3 M9, ADR-056).

Durable, idempotent-by-``jti`` revocation of issued tokens. Revocation is a
defense-in-depth on top of absolute expiry: a revoked token is rejected even
before its ``exp``.
"""

from __future__ import annotations

import abc


class TokenRevocationStore(abc.ABC):
    @abc.abstractmethod
    def add(self, jti: str, expires_at: str) -> None:
        """Revoke a token id (idempotent; re-adding is a no-op)."""

    @abc.abstractmethod
    def is_revoked(self, jti: str, *, now: str) -> bool:
        """True when ``jti`` is revoked and its revocation is not yet past the
        token's absolute expiry."""

    @abc.abstractmethod
    def prune(self, *, now: str) -> int:
        """Delete revocations whose expiry has passed; returns rows removed."""
