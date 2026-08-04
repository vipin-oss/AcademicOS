"""Command (CQRS intent) for pause / resume / cancel control actions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ControlIntakeSessionCommand:
    """Intent to control one session (which action is the use-case choice)."""

    session_id: str
