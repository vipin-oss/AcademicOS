"""Command (CQRS intent) for requesting a password-reset token."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.auth import ForgotPasswordInput


@dataclass
class ForgotPasswordCommand:
    """Intent to request a password-reset token for a username."""

    input: ForgotPasswordInput
