"""Application port: entity match decision store.

Stores professor decisions about entity matches:
- PENDING: match found, awaiting review
- CONFIRMED: professor confirmed the match → relationship created
- REJECTED: professor rejected the match → no relationship
- CONFLICT: conflicting evidence → requires review
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class MatchDecision(str, Enum):
    """Possible decisions for an entity match."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class EntityMatchRecord:
    """Persistent record of an entity match decision."""
    id: str
    source_doc_id: str
    target_doc_id: str
    confidence: float
    evidence: str  # JSON string of matching signals
    decision: MatchDecision
    decided_by: Optional[str]  # user ID who made the decision
    decided_at: Optional[datetime]
    created_at: datetime


class EntityMatchStore(abc.ABC):
    """Abstract store for entity match decisions."""

    @abc.abstractmethod
    def put(
        self,
        source_doc_id: str,
        target_doc_id: str,
        confidence: float,
        evidence: str,
        decision: MatchDecision = MatchDecision.PENDING,
        decided_by: Optional[str] = None,
    ) -> EntityMatchRecord:
        """Create or update a match decision. Idempotent by (source, target)."""

    @abc.abstractmethod
    def get(self, source_doc_id: str, target_doc_id: str) -> Optional[EntityMatchRecord]:
        """Get a specific match decision."""

    @abc.abstractmethod
    def by_source(self, source_doc_id: str) -> list[EntityMatchRecord]:
        """Get all matches for a source document."""

    @abc.abstractmethod
    def pending_for_user(self, user_id: str) -> list[EntityMatchRecord]:
        """Get all pending matches for documents owned by a user."""

    @abc.abstractmethod
    def update_decision(
        self,
        source_doc_id: str,
        target_doc_id: str,
        decision: MatchDecision,
        decided_by: str,
    ) -> Optional[EntityMatchRecord]:
        """Update the decision for a match. Returns None if not found."""
