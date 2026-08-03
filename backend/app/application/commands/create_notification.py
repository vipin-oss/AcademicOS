"""Boundary command: Create a personal notification."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.productivity import CreateNotificationInput


@dataclass
class CreateNotificationCommand:
    input: CreateNotificationInput
