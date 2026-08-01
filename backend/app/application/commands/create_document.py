"""Command (CQRS intent) for uploading a Document.

Mirrors ``CreateObjectCommand``: the immutable intent simply wraps the boundary
``CreateDocumentInput`` DTO — no duplicated fields.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.document import CreateDocumentInput


@dataclass
class CreateDocumentCommand:
    """Intent to upload a Document (file facts + metadata + optional link)."""

    input: CreateDocumentInput
