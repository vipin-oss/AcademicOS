"""Document annotation DTOs (Sprint M10 — Native Document Viewer).

Annotations are user content attached to a document page:

- ``highlight`` — payload: ``{"rects": [{"x0","y0","x1","y1"}, ...]}``
  (PDF page units) plus the matched ``text`` the highlight came from;
- ``note`` — payload: ``{"text": str, "x": float?, "y": float?}``;
- ``bookmark`` — payload: ``{"label": str?}`` (page carries the mark).

The record is validated here (identity, type domain, 1-based page,
non-empty payload) — the same invariant doctrine as ReviewDecision.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

ANNOTATION_HIGHLIGHT = "highlight"
ANNOTATION_NOTE = "note"
ANNOTATION_BOOKMARK = "bookmark"
ANNOTATION_TYPES = (ANNOTATION_HIGHLIGHT, ANNOTATION_NOTE, ANNOTATION_BOOKMARK)


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


@dataclass(frozen=True)
class DocumentAnnotation:
    """One durable user annotation on a document page."""

    annotation_id: str
    document_id: str
    annotation_type: str
    page: int  # 1-based
    payload: dict[str, Any]
    created_by: str
    created_at: str = ""
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.annotation_id or not self.document_id or not self.created_by:
            raise ValueError("DocumentAnnotation identity fields must not be empty.")
        if self.annotation_type not in ANNOTATION_TYPES:
            raise ValueError(f"Unknown annotation type: {self.annotation_type!r}")
        if self.page < 1:
            raise ValueError("DocumentAnnotation page must be >= 1.")
        if not isinstance(self.payload, dict) or not self.payload:
            raise ValueError("DocumentAnnotation payload must be a non-empty object.")
        if not self.created_at:
            raise ValueError("DocumentAnnotation created_at must not be empty.")


def new_annotation(
    *,
    document_id: str,
    annotation_type: str,
    page: int,
    payload: dict[str, Any],
    created_by: str,
) -> DocumentAnnotation:
    """Factory: generates the idempotency key + timestamp once."""
    return DocumentAnnotation(
        annotation_id=str(uuid.uuid4()),
        document_id=document_id,
        annotation_type=annotation_type,
        page=page,
        payload=payload,
        created_by=created_by,
        created_at=_utcnow_iso(),
    )


def as_annotation_dict(annotation: DocumentAnnotation) -> dict[str, Any]:
    return {
        "annotation_id": annotation.annotation_id,
        "document_id": annotation.document_id,
        "annotation_type": annotation.annotation_type,
        "page": annotation.page,
        "payload": annotation.payload,
        "created_by": annotation.created_by,
        "created_at": annotation.created_at,
        "updated_at": annotation.updated_at,
    }


__all__ = [
    "ANNOTATION_BOOKMARK",
    "ANNOTATION_HIGHLIGHT",
    "ANNOTATION_NOTE",
    "ANNOTATION_TYPES",
    "DocumentAnnotation",
    "as_annotation_dict",
    "new_annotation",
]
