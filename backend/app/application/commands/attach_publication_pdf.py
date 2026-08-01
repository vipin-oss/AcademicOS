"""Command (CQRS intent) for attaching/replacing the primary PDF of a Publication.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class AttachPublicationPdfCommand:
    """Intent to attach a PDF blob to the Publication ``object_id``."""

    object_id: ObjectId
    file_name: str
    content: bytes
    mime_type: str
    actor: str = "system"
