"""Command (CQRS intent) for attaching/replacing a Faculty profile photo."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class AttachFacultyPhotoCommand:
    """Intent to attach (or replace) a profile photo blob via FileStorage."""

    object_id: ObjectId
    file_name: str
    content: bytes
    mime_type: str
    actor: str = "system"
