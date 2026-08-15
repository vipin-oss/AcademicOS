"""Port: document-annotation persistence (Sprint M10).

The single seam between the viewer (application) and durable storage
(infrastructure) — the same doctrine as ``review_decision_store``: the
port carries the application ``DocumentAnnotation`` record and the
adapter owns the table. Annotations are mutable user content, so the
port supports update and delete (unlike the append-only audit stores).
"""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only — no runtime dependency (no cycle)
    from app.application.dtos.annotation import DocumentAnnotation


class AnnotationStore(abc.ABC):
    @abc.abstractmethod
    def add(self, annotation: DocumentAnnotation) -> DocumentAnnotation:
        """Insert one annotation row; returns it as stored."""

    @abc.abstractmethod
    def get(self, annotation_id: str) -> DocumentAnnotation | None:
        """The annotation with ``annotation_id``, or None."""

    @abc.abstractmethod
    def by_document(self, document_id: str) -> list[DocumentAnnotation]:
        """A document's annotations, page then creation ordered."""

    @abc.abstractmethod
    def update(self, annotation: DocumentAnnotation) -> DocumentAnnotation:
        """Replace a stored annotation (same id)."""

    @abc.abstractmethod
    def delete(self, annotation_id: str) -> bool:
        """Remove an annotation row; False when it did not exist."""
