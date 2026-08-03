"""Query: List assistant conversations (pinned first, then most recent)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListConversationsQuery:
    page: int = 1
    page_size: int = 50
