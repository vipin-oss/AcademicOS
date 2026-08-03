"""Boundary command: Delete a notification."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteNotificationCommand:
    object_id: str
