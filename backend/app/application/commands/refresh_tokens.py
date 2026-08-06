"""Command (CQRS intent) for refreshing an expired access token."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.auth import RefreshInput


@dataclass
class RefreshTokensCommand:
    """Intent to exchange a valid refresh token for a fresh token pair."""

    input: RefreshInput
