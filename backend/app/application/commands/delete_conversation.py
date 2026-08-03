"""Command: Delete an assistant conversation (and its embedded messages)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.assistant import DeleteConversationInput


@dataclass
class DeleteConversationCommand:
    input: DeleteConversationInput
