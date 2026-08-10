"""Document-content projection rebuild (M27).

Reconstructs the ``document_contents`` projection from durable state,
deterministically: every DOCUMENT object -> its linked INTAKE_ITEM
(``BELONGS_TO`` edge written by the Commit Engine) -> the extracted-text
blob in file storage (the source of truth). Documents without an intake
item (direct uploads) or without extracted text have no content row —
their title/metadata remain searchable through ``search_documents``.

The rebuild mirrors the search-projection contract: derived data only,
idempotent (rows are keyed by object_id), never mutates authoritative
state. Runs inside one transaction (delete-all + re-upsert), exactly like
``SearchIndexApplier.rebuild``.
"""
from __future__ import annotations

import logging

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.application.ports.file_storage import FileStorage
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind
from app.infrastructure.db.models.document_content_model import DocumentContentModel
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
    commit_with_retry,
)

_log = logging.getLogger(__name__)

#: Intake item metadata keys (kept local — the rebuild reads extraction
#: descriptors the same way the extracted-text use case does).
KEY_EXTRACTION = "intake.extraction"


def rebuild_document_contents(session: Session, storage: FileStorage) -> dict:
    """Rebuild the content projection for every document with extracted text.

    Returns ``{"indexed": n, "skipped": n}`` — ``skipped`` counts documents
    without an intake item or without an extracted-text blob (nothing to
    index; not an error).
    """
    repo: ObjectRepository = SQLAlchemyObjectRepository(session)
    documents = repo.find_by_type(ObjectType.DOCUMENT)
    indexed = 0
    skipped = 0
    rows: list[DocumentContentModel] = []

    for doc in documents:
        item_ids = [
            rel.target
            for rel in doc.relationships
            if rel.kind is RelationshipKind.BELONGS_TO
        ]
        text: str | None = None
        source_item_id = ""
        for item_id in item_ids:
            item = repo.get_by_id(item_id)
            if item is None or item.object_type is not ObjectType.INTAKE_ITEM:
                continue
            descriptor = _json_decode(item.metadata.get_value(KEY_EXTRACTION), None)
            text_key = (
                descriptor.get("text_key")
                if isinstance(descriptor, dict)
                else None
            )
            if not text_key or not storage.exists(text_key):
                continue
            try:
                text = storage.read(text_key).decode("utf-8")
            except Exception:  # noqa: BLE001 — a missing/corrupt blob skips
                _log.warning(
                    "Content rebuild: cannot read text blob %r for %s",
                    text_key, doc.id,
                )
                text = None
            if text:
                source_item_id = str(item_id)
                break
        if not text:
            skipped += 1
            continue
        rows.append(
            DocumentContentModel(
                object_id=str(doc.id),
                version=doc.version,
                content_text=text,
                source_item_id=source_item_id,
                created_at=_utcnow_iso(),
            )
        )
        indexed += 1

    def write() -> None:
        session.execute(delete(DocumentContentModel))
        for row in rows:
            session.add(row)

    commit_with_retry(session, write)
    return {"indexed": indexed, "skipped": skipped}


def _json_decode(raw, default):
    import json

    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def _utcnow_iso() -> str:
    import datetime as dt

    return dt.datetime.now(dt.UTC).isoformat()
