"""Query: Load one assistant conversation with its full message thread."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetConversationQuery:
    conversation_id: str
