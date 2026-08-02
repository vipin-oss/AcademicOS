"""Command (CQRS intent) for attaching/replacing an Assignment's file."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class AttachAssignmentFileCommand:
    """Intent to attach (or replace) the Assignment's reference file
    (question paper / instructions PDF). Same storage idiom as the
    publication primary PDF."""

    object_id: ObjectId
    file_name: str
    content: bytes
    mime_type: str
    actor: str = "system"
