"""Command (CQRS intent) for authenticating a user."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.auth import LoginInput


@dataclass
class LoginUserCommand:
    """Intent to verify credentials and issue tokens (401 on failure)."""

    input: LoginInput
