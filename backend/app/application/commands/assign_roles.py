"""Command (CQRS intent) for assigning roles to a user."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.auth import AssignRolesInput


@dataclass
class AssignRolesCommand:
    """Intent to replace a user's roles (admin-only operation)."""

    input: AssignRolesInput
