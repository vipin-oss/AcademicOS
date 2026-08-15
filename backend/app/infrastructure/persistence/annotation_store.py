"""SQLAlchemy adapter for the ``AnnotationStore`` port (Sprint M10).

The single writer of the ``document_annotations`` table, shaped like the
``SQLReviewDecisionStore``: a thin ``Session`` wrapper mapping
``DocumentAnnotation`` records to rows and back, one commit per write.
Row mapping is the only place that touches the table.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.application.dtos.annotation import DocumentAnnotation
from app.application.ports.annotation_store import AnnotationStore
from app.infrastructure.db.models.annotation_model import DocumentAnnotationModel


class SQLAnnotationStore(AnnotationStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------- writes
    def add(self, annotation: DocumentAnnotation) -> DocumentAnnotation:
        self._session.add(
            DocumentAnnotationModel(
                annotation_id=annotation.annotation_id,
                document_id=annotation.document_id,
                annotation_type=annotation.annotation_type,
                page=annotation.page,
                payload=annotation.payload,
                created_by=annotation.created_by,
                created_at=annotation.created_at,
                updated_at=annotation.updated_at,
            )
        )
        self._session.commit()
        return annotation

    def update(self, annotation: DocumentAnnotation) -> DocumentAnnotation:
        self._session.execute(
            update(DocumentAnnotationModel)
            .where(
                DocumentAnnotationModel.annotation_id == annotation.annotation_id
            )
            .values(
                annotation_type=annotation.annotation_type,
                page=annotation.page,
                payload=annotation.payload,
                updated_at=annotation.updated_at,
            )
        )
        self._session.commit()
        return annotation

    def delete(self, annotation_id: str) -> bool:
        result = self._session.execute(
            sa_delete(DocumentAnnotationModel).where(
                DocumentAnnotationModel.annotation_id == annotation_id
            )
        )
        self._session.commit()
        return (result.rowcount or 0) > 0

    # -------------------------------------------------------------- reads
    def get(self, annotation_id: str) -> DocumentAnnotation | None:
        rows = (
            self._session.execute(
                select(DocumentAnnotationModel).where(
                    DocumentAnnotationModel.annotation_id == annotation_id
                )
            )
            .scalars()
            .all()
        )
        return self._from_row(rows[0]) if rows else None

    def by_document(self, document_id: str) -> list[DocumentAnnotation]:
        rows = (
            self._session.execute(
                select(DocumentAnnotationModel)
                .where(DocumentAnnotationModel.document_id == document_id)
                .order_by(
                    DocumentAnnotationModel.page.asc(),
                    DocumentAnnotationModel.created_at.asc(),
                    DocumentAnnotationModel.id.asc(),
                )
            )
            .scalars()
            .all()
        )
        return [self._from_row(row) for row in rows]

    # ------------------------------------------------------------- mapping
    @staticmethod
    def _from_row(row: DocumentAnnotationModel) -> DocumentAnnotation:
        return DocumentAnnotation(
            annotation_id=row.annotation_id,
            document_id=row.document_id,
            annotation_type=row.annotation_type,
            page=row.page,
            payload=row.payload,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


__all__ = ["SQLAnnotationStore"]
