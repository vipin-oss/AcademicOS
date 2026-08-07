"""Document annotation service (Sprint M10 — Native Document Viewer).

The single application seam for document annotations and the viewer's
extracted-text lookup:

- create/list/update/delete annotations over the ``AnnotationStore``,
  with the document-exists guard (annotations only attach to real
  DOCUMENT objects) and the record invariants from ``annotation.py``;
- ``extracted_text`` resolves a document's linked INTAKE_ITEM (the
  BELONGS_TO edge written by the M9 Commit Engine) and reuses the
  existing ``GetIntakeExtractedTextUseCase`` — the viewer's right panel
  shows the same text the pipeline extracted, with zero changes to the
  extraction machinery (M1–M9 behaviour untouched).
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from app.application.dtos.annotation import (
    DocumentAnnotation,
    new_annotation,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.annotation_store import AnnotationStore
from app.application.ports.file_storage import FileStorage
from app.application.queries.get_intake_extracted_text import GetIntakeExtractedTextQuery
from app.application.use_cases.intake.get_extracted_text import GetIntakeExtractedTextUseCase
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind
from app.domain.value_objects.object_id import ObjectId


class DocumentAnnotationService:
    def __init__(
        self,
        repository: ObjectRepository,
        store: AnnotationStore,
    ) -> None:
        self._repository = repository
        self._store = store

    # ------------------------------------------------------------ lifecycle
    def create(
        self,
        *,
        document_id: str,
        annotation_type: str,
        page: int,
        payload: dict[str, Any],
        created_by: str,
    ) -> DocumentAnnotation:
        self._require_document(document_id)
        annotation = new_annotation(
            document_id=document_id,
            annotation_type=annotation_type,
            page=page,
            payload=payload,
            created_by=created_by,
        )
        return self._store.add(annotation)

    def list(self, document_id: str) -> list[DocumentAnnotation]:
        self._require_document(document_id)
        return self._store.by_document(document_id)

    def update(
        self,
        annotation_id: str,
        *,
        page: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> DocumentAnnotation:
        current = self._store.get(annotation_id)
        if current is None:
            raise ObjectNotFoundError(f"Annotation not found: {annotation_id}")
        updated = DocumentAnnotation(
            annotation_id=current.annotation_id,
            document_id=current.document_id,
            annotation_type=current.annotation_type,
            page=page if page is not None else current.page,
            payload=payload if payload is not None else current.payload,
            created_by=current.created_by,
            created_at=current.created_at,
            updated_at=dt.datetime.now(dt.UTC).isoformat(),
        )
        return self._store.update(updated)

    def delete(self, annotation_id: str) -> None:
        if not self._store.delete(annotation_id):
            raise ObjectNotFoundError(f"Annotation not found: {annotation_id}")

    # ------------------------------------------------------- extracted text
    def extracted_text(
        self,
        document_id: str,
        storage: FileStorage,
    ) -> dict[str, Any] | None:
        """The document's linked intake-item extracted text (M10 viewer).

        Resolves the BELONGS_TO edge to the intake item that produced
        this document, then reuses the existing extraction-text use case.
        ``None`` when the document has no linked item / no extracted
        text (the viewer shows an honest empty state).
        """
        linked = self._repository.find_related(
            ObjectId(document_id), RelationshipKind.BELONGS_TO
        )
        if not linked:
            return None
        item = self._repository.get_by_id(linked[0])
        if item is None or item.object_type is not ObjectType.INTAKE_ITEM:
            return None
        session_id = item.metadata.get_value("intake.session_id")
        if not session_id:
            return None
        try:
            text = GetIntakeExtractedTextUseCase(self._repository, storage).execute(
                GetIntakeExtractedTextQuery(
                    session_id=session_id, item_id=str(item.id)
                )
            )
        except ObjectNotFoundError:
            return None
        return {"text": text, "session_id": session_id, "item_id": str(item.id)}

    # --------------------------------------------------------------- guards
    def _require_document(self, document_id: str) -> None:
        try:
            obj = self._repository.get_by_id(ObjectId(document_id))
        except ValueError as exc:
            raise ObjectNotFoundError(f"Document not found: {document_id}") from exc
        if obj is None or obj.object_type is not ObjectType.DOCUMENT:
            raise ObjectNotFoundError(f"Document not found: {document_id}")


__all__ = ["DocumentAnnotationService"]
