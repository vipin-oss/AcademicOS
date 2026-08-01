"""Input validation for document use cases.

Mirrors ``validators/object.py``: validation runs at the boundary, before the
domain is touched, raising the application-layer ``ValidationError`` so the
presentation layer maps it to a client error. Pure and framework-free.
"""
from __future__ import annotations

from app.application.dtos.document import CreateDocumentInput, UpdateDocumentInput
from app.application.exceptions import ValidationError
from app.application.queries.list_documents import ListDocumentsQuery
from app.domain.value_objects.enums import ObjectStatus

# File-type taxonomy mirrored from the Documents UI (presentation vocabulary,
# stored as metadata — never a separate domain enum).
DOCUMENT_TYPES = (
    "pdf",
    "docx",
    "xlsx",
    "pptx",
    "txt",
    "zip",
    "image",
    "video",
    "unknown",
)

_CREATABLE_STATUSES = (ObjectStatus.DRAFT, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED)


def validate_create_document_input(dto: CreateDocumentInput) -> list[str]:
    errors: list[str] = []
    if not dto.title or not dto.title.strip():
        errors.append("Title must not be empty.")
    if not dto.uploaded_by or not dto.uploaded_by.strip():
        errors.append("uploaded_by must identify an actor.")
    if dto.document_type not in DOCUMENT_TYPES:
        errors.append(f"document_type must be one of: {', '.join(DOCUMENT_TYPES)}.")
    if dto.status not in _CREATABLE_STATUSES:
        errors.append("Initial status must be DRAFT, ACTIVE, or ARCHIVED.")
    if dto.file_size < 0:
        errors.append("file_size must not be negative.")
    for tag in dto.tags:
        if not tag or not str(tag).strip():
            errors.append("Tags must not be empty.")
            break
    return errors


def validate_update_document_input(dto: UpdateDocumentInput) -> list[str]:
    errors: list[str] = []
    if not dto.actor or not dto.actor.strip():
        errors.append("actor must identify who performs the update.")
    if dto.title is not None and not dto.title.strip():
        errors.append("Title must not be empty.")
    if dto.document_type is not None and dto.document_type not in DOCUMENT_TYPES:
        errors.append(f"document_type must be one of: {', '.join(DOCUMENT_TYPES)}.")
    if dto.status is not None and dto.status not in _CREATABLE_STATUSES:
        errors.append("Status must be DRAFT, ACTIVE, or ARCHIVED.")
    if dto.tags is not None:
        for tag in dto.tags:
            if not tag or not str(tag).strip():
                errors.append("Tags must not be empty.")
                break
    return errors


def validate_list_documents_query(query: ListDocumentsQuery) -> list[str]:
    errors: list[str] = []
    if query.page < 1:
        errors.append("page must be >= 1.")
    if query.page_size < 1:
        errors.append("page_size must be >= 1.")
    if query.page_size > 100:
        errors.append("page_size must be <= 100.")
    return errors


def assert_valid_create_document_input(dto: CreateDocumentInput) -> None:
    errors = validate_create_document_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_update_document_input(dto: UpdateDocumentInput) -> None:
    errors = validate_update_document_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_list_documents_query(query: ListDocumentsQuery) -> None:
    errors = validate_list_documents_query(query)
    if errors:
        raise ValidationError("; ".join(errors))
