"""Command: Start a new (empty) assistant conversation."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.assistant import CreateConversationInput


@dataclass
class CreateConversationCommand:
    input: CreateConversationInput
