"""Data Transfer Objects for the Document use cases.

Boundary contract for the Documents slice — mirrors ``dtos/object.py`` exactly:
plain dataclasses (framework-free), depending only on Domain types. A Document
is a Universal Object with ``object_type = document`` (Blueprint §2); its
file facts and taxonomy ride in the seven-layer metadata record, and its link
to another Object is an asserted ``belongs_to`` relationship (Blueprint §4).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, RelationshipKind
from app.domain.value_objects.object_id import ObjectId

# Metadata keys carrying the document projection (frozen convention).
KEY_DOCUMENT_TYPE = "document_type"
KEY_DESCRIPTION = "description"
KEY_TAGS = "tags"
KEY_FILE_NAME = "file_name"
KEY_FILE_SIZE = "file_size"
KEY_MIME_TYPE = "mime_type"
KEY_FILE_PATH = "file_path"

# Relationship kinds that express "this document belongs to that Object".
LINK_KINDS = (RelationshipKind.BELONGS_TO, RelationshipKind.ATTACHED_TO)


def linked_object_id(obj: UniversalObject) -> ObjectId | None:
    """First asserted structural link of this document, if any."""
    for rel in obj.relationships:
        if rel.kind in LINK_KINDS:
            return rel.target
    return None


def parse_tags(raw: str | None) -> list[str]:
    """Decode the stored tag list (JSON-encoded string in metadata)."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return [tag.strip() for tag in raw.split(",") if tag.strip()]
    if isinstance(value, list):
        return [str(tag) for tag in value]
    return []


def encode_tags(tags: list[str] | tuple[str, ...]) -> str:
    """Encode tags for storage as a single metadata value."""
    return json.dumps(list(tags), ensure_ascii=False)


@dataclass
class CreateDocumentInput:
    """Boundary input for uploading a Document (file + metadata)."""

    title: str
    document_type: str
    uploaded_by: str
    file_name: str
    file_size: int
    mime_type: str
    content: bytes
    status: ObjectStatus = ObjectStatus.DRAFT
    object_id: ObjectId | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()


@dataclass
class UpdateDocumentInput:
    """Boundary input for updating a Document (partial, no re-upload).

    ``object_id_provided`` distinguishes "leave the link alone" (field absent)
    from "unlink" (field explicitly null) — JSON-merge-patch semantics.
    """

    actor: str
    title: str | None = None
    document_type: str | None = None
    description: str | None = None
    tags: tuple[str, ...] | None = None
    status: ObjectStatus | None = None
    object_id: ObjectId | None = None
    object_id_provided: bool = False


@dataclass
class DocumentOutput:
    """Boundary output for every Document use case (single response shape)."""

    id: str
    title: str
    object_id: str | None
    object_type: str | None
    object_title: str | None
    document_type: str
    description: str | None
    tags: list[str]
    file_name: str
    file_size: int
    mime_type: str
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    file_path: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        linked: UniversalObject | None = None,
    ) -> DocumentOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        link_id = linked_object_id(obj)
        return DocumentOutput(
            id=str(obj.id),
            title=obj.title,
            object_id=str(link_id) if link_id is not None else None,
            object_type=linked.object_type.value if linked is not None else None,
            object_title=linked.title if linked is not None else None,
            document_type=meta.get(KEY_DOCUMENT_TYPE, "unknown"),
            description=meta.get(KEY_DESCRIPTION),
            tags=parse_tags(meta.get(KEY_TAGS)),
            file_name=meta.get(KEY_FILE_NAME, ""),
            file_size=int(meta.get(KEY_FILE_SIZE, 0) or 0),
            mime_type=meta.get(KEY_MIME_TYPE, ""),
            status=obj.status.value,
            version=obj.version,
            uploaded_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat()
                if obj.audit is not None and obj.audit.updated_at is not None
                else None
            ),
            file_path=meta.get(KEY_FILE_PATH),
            metadata=meta,
            events=[event.__class__.__name__ for event in events],
        )


@dataclass
class ListDocumentsResult:
    """Boundary result for a paginated listing of Documents."""

    items: list[DocumentOutput]
    total_count: int
    page: int
    page_size: int
