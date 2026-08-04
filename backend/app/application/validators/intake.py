"""Input validation for intake session creation.

Mirrors ``validators/document.py``: validation runs at the boundary, before
the domain is touched, raising the application-layer ``ValidationError``.
Filesystem existence checks live in the use case itself (they are part of the
business action, not the payload shape); this module validates shape only.
Pure and framework-free.
"""
from __future__ import annotations

from app.application.dtos.intake import (
    MAX_FILE_PATHS_REQUEST,
    CreateIntakeSessionInput,
    IntakeSourceKind,
)
from app.application.exceptions import ValidationError


def validate_create_intake_session_input(dto: CreateIntakeSessionInput) -> list[str]:
    errors: list[str] = []
    if dto.source_kind not in (IntakeSourceKind.FOLDER, IntakeSourceKind.FILES):
        errors.append("source_kind must be 'folder' or 'files'.")
    if dto.source_kind is IntakeSourceKind.FOLDER and (not dto.path or not dto.path.strip()):
        errors.append("path is required for a folder import.")
    if dto.source_kind is IntakeSourceKind.FILES:
        if not dto.paths:
            errors.append("paths must name at least one file.")
        elif len(dto.paths) > MAX_FILE_PATHS_REQUEST:
            errors.append(f"paths accepts at most {MAX_FILE_PATHS_REQUEST} files per drop.")
        elif any(not str(p).strip() for p in dto.paths):
            errors.append("paths must not contain empty entries.")
    if not dto.actor or not dto.actor.strip():
        errors.append("actor must identify who started the import.")
    if dto.title is not None and len(dto.title.strip()) > 200:
        errors.append("title must be at most 200 characters.")
    return errors


def assert_valid_create_intake_session_input(dto: CreateIntakeSessionInput) -> None:
    errors = validate_create_intake_session_input(dto)
    if errors:
        raise ValidationError(" ".join(errors))
