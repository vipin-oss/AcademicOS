"""Pure mapping between API request/response shapes and Application DTOs.

Mirrors ``object_mapper.py``: framework-free (no FastAPI/Pydantic/SQLAlchemy
imports) so it stays unit-testable without those dependencies.
"""
from __future__ import annotations

import json

from app.application.dtos.document import (
    CreateDocumentInput,
    DocumentOutput,
    UpdateDocumentInput,
)
from app.domain.value_objects.enums import ObjectStatus
from app.domain.value_objects.object_id import ObjectId


def parse_tags_field(raw: str | None) -> tuple[str, ...]:
    """Parse the multipart ``tags`` form field (a JSON-encoded string array)."""
    if not raw or not raw.strip():
        return ()
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise ValueError("tags must be a JSON-encoded array of strings.") from exc
    if not isinstance(value, list) or not all(isinstance(tag, str) for tag in value):
        raise ValueError("tags must be a JSON-encoded array of strings.")
    return tuple(value)


def parse_object_id_field(raw: str | None) -> ObjectId | None:
    """Parse an optional Object id form field (``obj:…`` handle or empty)."""
    if not raw or not raw.strip():
        return None
    return ObjectId.parse(raw.strip())


def to_create_input(
    *,
    title: str,
    document_type: str,
    uploaded_by: str,
    file_name: str,
    content: bytes,
    mime_type: str,
    object_id: str | None = None,
    description: str | None = None,
    tags: str | None = None,
    status: str = "draft",
) -> CreateDocumentInput:
    """Convert multipart primitives into the Application ``CreateDocumentInput``."""
    return CreateDocumentInput(
        title=title,
        document_type=document_type,
        uploaded_by=uploaded_by,
        file_name=file_name,
        file_size=len(content),
        mime_type=mime_type,
        content=content,
        status=ObjectStatus(status),
        object_id=parse_object_id_field(object_id),
        description=description.strip() if description else None,
        tags=parse_tags_field(tags),
    )


def to_update_input(
    *,
    actor: str,
    title: str | None = None,
    document_type: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    object_id: str | None = None,
    object_id_provided: bool = False,
) -> UpdateDocumentInput:
    """Convert the JSON PUT/PATCH body into the Application ``UpdateDocumentInput``."""
    return UpdateDocumentInput(
        actor=actor,
        title=title,
        document_type=document_type,
        description=description,
        tags=tuple(tags) if tags is not None else None,
        status=ObjectStatus(status) if status else None,
        object_id=parse_object_id_field(object_id),
        object_id_provided=object_id_provided,
    )


def to_response(out: DocumentOutput, *, url: str | None = None) -> dict:
    """Project an Application ``DocumentOutput`` into a JSON-serialisable dict."""
    return {
        "id": out.id,
        "title": out.title,
        "object_id": out.object_id,
        "object_type": out.object_type,
        "object_title": out.object_title,
        "document_type": out.document_type,
        "description": out.description,
        "tags": out.tags,
        "file_name": out.file_name,
        "file_size": out.file_size,
        "mime_type": out.mime_type,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.uploaded_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "url": url,
        "preview_url": None,
        "metadata": out.metadata,
        "events": out.events,
    }
