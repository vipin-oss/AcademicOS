"""Application port: token signing/verification (Sprint-1 auth foundation).

The application layer must never import infrastructure (guardrail), so the
auth use cases depend on this port; the infrastructure adapter wraps the
existing JWT utilities. Policy (claims shape, TTLs) stays in infrastructure
config; the port only exposes the verbs.
"""
from __future__ import annotations

import abc


class TokenService(abc.ABC):
    @abc.abstractmethod
    def create_access_token(self, subject: str) -> str:
        """Issue a short-lived access token for ``subject``."""

    @abc.abstractmethod
    def create_refresh_token(self, subject: str) -> str:
        """Issue a long-lived refresh token for ``subject``."""

    @abc.abstractmethod
    def create_reset_token(self, subject: str) -> str:
        """Issue a short-lived password-reset token for ``subject``."""

    @abc.abstractmethod
    def decode_token(self, token: str) -> dict:
        """Verify and decode a token. Raises on invalid/expired tokens."""
