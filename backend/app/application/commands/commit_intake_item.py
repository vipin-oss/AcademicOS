"""Command (CQRS intent) for committing one intake item to a Document."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CommitIntakeItemCommand:
    """Intent to promote one AWAITING_REVIEW intake item into a Document.

    Idempotent: committing an already-committed item raises a conflict
    carrying the existing document id.
    """

    item_id: str
    actor: str
