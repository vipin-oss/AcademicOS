"""Command (CQRS intent) for registering a user account."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.auth import RegisterUserInput


@dataclass
class RegisterUserCommand:
    """Intent to create a USER object (409 on duplicate username)."""

    input: RegisterUserInput
