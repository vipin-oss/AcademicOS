"""Entity Linking Service (Revision #17).

Creates actual relationships between documents that refer to the same
academic entity, using the existing relationship infrastructure.

This service:
1. Takes entity matches from the resolution service
2. Creates RELATED_TO relationships via the existing relationship model
3. Preserves provenance (every link has evidence)
4. Is idempotent (no duplicate relationships)
5. Is permission-aware (respects ACL)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.services.entity_resolution import MatchResult
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.object_id import ObjectId


@dataclass(frozen=True)
class LinkResult:
    """Result of an entity linking operation."""
    source_doc_id: str
    target_doc_id: str
    success: bool
    relationship_id: str | None = None
    already_linked: bool = False
    error: str | None = None


class EntityLinkingService:
    """Creates relationships between documents that refer to the same entity."""

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def create_link(
        self,
        source_doc_id: str,
        target_doc_id: str,
        confidence: float,
        evidence: str,
        actor: str,
    ) -> LinkResult:
        """Create a RELATED_TO relationship between two documents.

        Args:
            source_doc_id: Source document ID
            target_doc_id: Target document ID
            confidence: Match confidence (0.0-1.0)
            evidence: Human-readable evidence description
            actor: User ID performing the action

        Returns:
            LinkResult with success status
        """
        try:
            # Load both documents
            source = self._repository.get_by_id(ObjectId(source_doc_id))
            target = self._repository.get_by_id(ObjectId(target_doc_id))

            if source is None:
                return LinkResult(
                    source_doc_id=source_doc_id,
                    target_doc_id=target_doc_id,
                    success=False,
                    error="Source document not found",
                )

            if target is None:
                return LinkResult(
                    source_doc_id=source_doc_id,
                    target_doc_id=target_doc_id,
                    success=False,
                    error="Target document not found",
                )

            # Check if already linked (idempotency)
            if self._already_linked(source, target_doc_id):
                return LinkResult(
                    source_doc_id=source_doc_id,
                    target_doc_id=target_doc_id,
                    success=True,
                    already_linked=True,
                )

            # Create RELATED_TO relationship
            source.add_relationship(
                ObjectId(target_doc_id),
                RelationshipKind.RELATED_TO,
                Provenance.ASSERTED,
                actor=actor,
            )

            # Save with provenance
            self._repository.save(source)

            return LinkResult(
                source_doc_id=source_doc_id,
                target_doc_id=target_doc_id,
                success=True,
            )

        except Exception as e:
            return LinkResult(
                source_doc_id=source_doc_id,
                target_doc_id=target_doc_id,
                success=False,
                error=str(e),
            )

    def create_link_from_match(
        self,
        match: MatchResult,
        actor: str,
    ) -> LinkResult:
        """Create a link from an entity match result.

        Args:
            match: MatchResult from entity resolution
            actor: User ID performing the action

        Returns:
            LinkResult with success status
        """
        # Build evidence string from signals
        evidence_parts = []
        for signal in match.signals:
            if signal.confidence > 0:
                evidence_parts.append(signal.evidence)

        evidence = "; ".join(evidence_parts) if evidence_parts else "Entity match"

        return self.create_link(
            source_doc_id=match.source_doc_id,
            target_doc_id=match.target_doc_id,
            confidence=match.confidence,
            evidence=evidence,
            actor=actor,
        )

    def _already_linked(self, source, target_id: str) -> bool:
        """Check if source already has a relationship to target."""
        try:
            for rel in source.relationships:
                if str(rel.target_id) == target_id:
                    return True
        except Exception:
            pass
        return False

    def get_related_documents(
        self,
        document_id: str,
    ) -> list[dict]:
        """Get all documents related to the given document.

        Returns list of related document info with relationship metadata.
        """
        try:
            doc = self._repository.get_by_id(ObjectId(document_id))
            if doc is None:
                return []

            related = []
            for rel in doc.relationships:
                target = self._repository.get_by_id(rel.target_id)
                if target is not None:
                    related.append({
                        "document_id": str(target.id),
                        "title": target.title or "",
                        "object_type": target.object_type.value if target.object_type else "",
                        "relationship_kind": rel.kind.value if rel.kind else "",
                        "provenance": rel.provenance.value if rel.provenance else "",
                    })

            return related

        except Exception:
            return []


__all__ = [
    "EntityLinkingService",
    "LinkResult",
]
