"""Boundary command: Update a notification state (read/pin/archive/snooze)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.productivity import UpdateNotificationInput


@dataclass
class UpdateNotificationCommand:
    object_id: str
    input: UpdateNotificationInput
