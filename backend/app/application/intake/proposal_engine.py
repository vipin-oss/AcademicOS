"""Proposal Engine (Sprint-3 M2) — generates reviewable commit proposals.

Coordinates only. The proposal is built deterministically from the item's
real pipeline facts (extension, mime, size, hash, extraction descriptor),
persisted as ``intake.proposal`` item metadata, and later reviewed
(P4) before the item is committed by the Commit Engine (the ONLY
component allowed to create documents).

Nothing here creates Documents, edges, or any object — generation and
persistence are pure item-metadata operations, reusing the existing
metadata machinery.
"""
from __future__ import annotations

import json

from app.application.dtos.intake import (
    KEY_EXTENSION,
    KEY_MIME_TYPE,
    KEY_PROPOSAL,
    KEY_SIZE_BYTES,
    ItemProposal,
    _extraction_dict_of,
    json_decode,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.validators.document import DOCUMENT_TYPES
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer, Provenance
from app.domain.value_objects.object_id import ObjectId


def proposal_from_item(
    *,
    title: str,
    document_type: str,
    extension: str | None,
    size_bytes: int,
    mime_type: str | None,
    char_count: int | None,
) -> ItemProposal:
    """Deterministic proposal from the item's real facts.

    - document_type: the file extension when it is a supported document
      type, else ``unknown``.
    - description: a human-readable factual summary (never fabricated
      content).
    - confidence: grounded on whether extraction produced text (1.0) or
      the type is only inferred from the extension (0.6).
    """
    effective_type = extension if extension in DOCUMENT_TYPES else "unknown"
    description = (
        f"{extension.upper() if extension else 'Unknown'} file, "
        f"{size_bytes} bytes"
        + (f", {mime_type}" if mime_type else "")
        + (f", {char_count} characters extracted" if char_count else "")
    )
    confidence = 1.0 if char_count else 0.6
    return ItemProposal(
        title=title,
        document_type=effective_type,
        description=description,
        confidence=confidence,
    )


class ProposalEngineService:
    """Generates and persists one proposal per item (idempotent)."""

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def generate(self, item_id: str) -> ItemProposal:
        item = self._repository.get_by_id(ObjectId(item_id))
        if item is None or item.object_type is not ObjectType.INTAKE_ITEM:
            raise ObjectNotFoundError(f"Intake item not found: {item_id}")

        descriptor = _extraction_dict_of(item)
        proposal = proposal_from_item(
            title=item.title,
            document_type=item.metadata.get_value(KEY_EXTENSION) or "",
            extension=item.metadata.get_value(KEY_EXTENSION) or "",
            size_bytes=int(item.metadata.get_value(KEY_SIZE_BYTES) or 0),
            mime_type=item.metadata.get_value(KEY_MIME_TYPE),
            char_count=int(descriptor.get("char_count") or 0) if descriptor else None,
        )

        # Persist as system-layer item metadata (idempotent replace).
        item.set_metadata(
            MetadataEntry(
                KEY_PROPOSAL,
                json.dumps(proposal.__dict__),
                MetadataLayer.L1_SYSTEM,
                Provenance.SYSTEM,
            ),
            actor="intake",
        )
        self._repository.save(item)
        return proposal

    def get(self, item_id: str) -> ItemProposal:
        """The item's current proposal, or a ValidationError when absent."""
        item = self._repository.get_by_id(ObjectId(item_id))
        if item is None or item.object_type is not ObjectType.INTAKE_ITEM:
            raise ObjectNotFoundError(f"Intake item not found: {item_id}")
        raw = item.metadata.get_value(KEY_PROPOSAL)
        data = json_decode(raw, None)
        if not isinstance(data, dict):
            raise ValidationError("Item has no proposal; generate one first.")
        return ItemProposal(**{k: data[k] for k in ("title", "document_type", "description", "confidence")})


class ProposalReviewService:
    """Human review of a generated proposal (Sprint-3 M2 P4).

    Updates are validated against the same document-type vocabulary the
    commit path uses, so a reviewed proposal always commits cleanly.
    """

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository
        self._generator = ProposalEngineService(repository)

    def update(self, item_id: str, *, title: str, document_type: str, description: str, actor: str) -> ItemProposal:
        item = self._repository.get_by_id(ObjectId(item_id))
        if item is None or item.object_type is not ObjectType.INTAKE_ITEM:
            raise ObjectNotFoundError(f"Intake item not found: {item_id}")
        if not item.metadata.get_value(KEY_PROPOSAL):
            raise ValidationError("Item has no proposal; generate one first.")

        if not title.strip():
            raise ValidationError("Proposal title must not be empty.")
        if document_type not in DOCUMENT_TYPES:
            raise ValidationError(
                f"document_type must be one of: {', '.join(DOCUMENT_TYPES)}."
            )

        proposal = ItemProposal(
            title=title.strip(),
            document_type=document_type,
            description=description.strip(),
            confidence=1.0,  # human-confirmed
        )
        item.set_metadata(
            MetadataEntry(
                KEY_PROPOSAL,
                json.dumps(proposal.__dict__),
                MetadataLayer.L1_SYSTEM,
                Provenance.SYSTEM,
            ),
            actor=actor,
        )
        self._repository.save(item)
        return proposal

    def regenerate(self, item_id: str, actor: str) -> ItemProposal:
        """Discard human edits and regenerate from the item's facts."""
        item = self._repository.get_by_id(ObjectId(item_id))
        if item is None or item.object_type is not ObjectType.INTAKE_ITEM:
            raise ObjectNotFoundError(f"Intake item not found: {item_id}")
        # Drop the stored proposal so generate() rebuilds it fresh.
        item.set_metadata(
            MetadataEntry(KEY_PROPOSAL, "", MetadataLayer.L1_SYSTEM, Provenance.SYSTEM),
            actor=actor,
        )
        self._repository.save(item)
        return self._generator.generate(item_id)
