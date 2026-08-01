"""Pure mapping between API request/response shapes and Application DTOs.

Framework-free (no FastAPI/Pydantic/SQLAlchemy imports) so it is unit-testable
without those dependencies.
"""
from __future__ import annotations

from app.application.dtos.object import CreateObjectInput, UpdateObjectInput
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


def to_create_input(
    *,
    object_type: str,
    title: str,
    created_by: str,
    object_id: str | None = None,
    status: str = "draft",
    metadata: list[dict] | None = None,
) -> CreateObjectInput:
    """Convert API primitives into the Application-layer ``CreateObjectInput`` DTO."""
    entries = None
    if metadata:
        entries = tuple(
            MetadataEntry(
                key=m["key"],
                value=m["value"],
                layer=MetadataLayer(int(m.get("layer", MetadataLayer.L6_HUMAN_ASSERTED))),
                source=Provenance(m.get("source", Provenance.ASSERTED)),
                confidence=m.get("confidence"),
            )
            for m in metadata
        )
    return CreateObjectInput(
        object_type=ObjectType(object_type),
        title=title,
        created_by=created_by,
        object_id=ObjectId(object_id) if object_id else None,
        status=ObjectStatus(status),
        metadata=Metadata(entries=entries) if entries else None,
    )


def to_update_input(
    *,
    object_id: str,
    updated_by: str,
    status: str | None = None,
    metadata: list[dict] | None = None,
) -> UpdateObjectInput:
    """Convert API primitives into the Application-layer ``UpdateObjectInput`` DTO."""
    entries = None
    if metadata:
        entries = tuple(
            MetadataEntry(
                key=m["key"],
                value=m["value"],
                layer=MetadataLayer(int(m.get("layer", MetadataLayer.L6_HUMAN_ASSERTED))),
                source=Provenance(m.get("source", Provenance.ASSERTED)),
                confidence=m.get("confidence"),
            )
            for m in metadata
        )
    return UpdateObjectInput(
        updated_by=updated_by,
        status=ObjectStatus(status) if status else None,
        metadata=Metadata(entries=entries) if entries else None,
    )


def to_response(out) -> dict:
    """Project an Application ``CreateObjectOutput`` into a JSON-serialisable dict."""
    return {
        "id": out.id,
        "object_type": out.object_type,
        "title": out.title,
        "status": out.status,
        "version": out.version,
        "created_by": out.created_by,
        "created_at": out.created_at,
        "metadata": out.metadata,
        "events": out.events,
    }
