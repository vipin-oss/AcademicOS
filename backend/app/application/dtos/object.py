"""Data Transfer Objects for the Object use cases.

DTOs are the boundary contract: the presentation layer builds an input DTO and
receives an output DTO. They depend on domain *types* (allowed — the
Application layer depends on the Domain) but carry no behaviour. Kept
framework-free (dataclasses) so the Application layer stays infrastructure-free.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import MetadataLayer, ObjectStatus, ObjectType
from app.domain.value_objects.metadata import Metadata
from app.domain.value_objects.object_id import ObjectId


@dataclass
class CreateObjectInput:
    """Boundary input for creating a Universal Object."""

    object_type: ObjectType
    title: str
    created_by: str
    object_id: ObjectId | None = None
    status: ObjectStatus = ObjectStatus.DRAFT
    metadata: Metadata | None = None


@dataclass
class UpdateObjectInput:
    """Boundary input for updating a Universal Object (partial)."""

    updated_by: str
    status: ObjectStatus | None = None
    metadata: Metadata | None = None


@dataclass
class CreateObjectOutput:
    """Boundary output returned after a Universal Object is created."""

    id: str
    object_type: str
    title: str
    status: str
    version: int
    created_by: str
    created_at: str
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(obj: UniversalObject, events: list) -> CreateObjectOutput:
        return CreateObjectOutput(
            id=str(obj.id),
            object_type=obj.object_type.value,
            title=obj.title,
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            metadata={
                e.key: e.value
                for e in obj.metadata.entries
                if e.layer is not MetadataLayer.L1_SYSTEM
            },
            events=[e.__class__.__name__ for e in events],
        )


@dataclass
class ListObjectsResult:
    """Boundary result for a paginated listing of Objects."""

    items: list[CreateObjectOutput]
    total_count: int
    page: int
    page_size: int
