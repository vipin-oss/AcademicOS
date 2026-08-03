"""Command: Rename / pin / unpin an assistant conversation (verbatim merge)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.assistant import UpdateConversationInput


@dataclass
class UpdateConversationCommand:
    input: UpdateConversationInput
