"""Command (CQRS intent) for resetting a password via a reset token."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.auth import ResetPasswordInput


@dataclass
class ResetPasswordCommand:
    """Intent to set a new password with a valid reset token."""

    input: ResetPasswordInput
