"""Document-content + chunk projection rebuild (M27 + P0 knowledge layer).

Reconstructs the ``document_contents`` AND ``document_chunks`` projections
from durable state, deterministically:

- DOCUMENT object -> linked INTAKE_ITEM (``BELONGS_TO``) -> extraction
  descriptor ``text_key`` -> extracted-text blob (intake origin);
- P0: documents WITHOUT an intake item (DIRECT UPLOADS) are resolved via
  their stored blob (``file_name`` metadata key ``file_name`` is NOT the
  blob key; the authoritative key is ``file_path``) -> parse with the
  existing parser registry -> normalized text.

Every row carries the normalized-content sha256 (``content_hash``); chunk
rows are derived from the same normalized text with the same deterministic
chunker the outbox applier uses, so:

    IncrementalProjection(S) == RebuiltProjection(S)

holds per object (content hash equality + ordered chunk-set equality).

Runs inside ONE transaction (delete-all + re-upsert), idempotent, derived
data only — never mutates authoritative state. Mirrors
``SearchIndexApplier.rebuild``.
"""
from __future__ import annotations

import logging

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.application.ports.file_storage import FileStorage
from app.application.services.document_chunking import Chunk, chunk_text, content_hash
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel
from app.infrastructure.db.models.document_content_model import DocumentContentModel
from app.infrastructure.db.models.document_identity_model import DocumentIdentityModel
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.persistence.search_mapping import to_search_document
from app.infrastructure.persistence.document_identity_store import SQLDocumentIdentityStore
from app.infrastructure.search.fts import SQLFTSRepository
from sqlalchemy.exc import OperationalError as _OperationalError
from app.infrastructure.extraction import build_document_parsers
from app.application.dtos.extraction import format_of
from app.application.dtos.document import KEY_FILE_PATH, KEY_FILE_NAME
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
    commit_with_retry,
)

_log = logging.getLogger(__name__)

#: Intake item metadata keys (kept local — the rebuild reads extraction
#: descriptors the same way the extracted-text use case does).
KEY_EXTRACTION = "intake.extraction"


def rebuild_document_contents(session: Session, storage: FileStorage) -> dict:
    """Rebuild content + chunk projections for every document with text.

    Returns ``{"indexed": n, "skipped": n, "chunked": n}``
    (``skipped`` = documents with no extractable text; ``chunked`` =
    documents whose chunks were (re)created). The rebuild is a
    delete-all + re-upsert, so every indexed document is rewritten —
    equivalence with the incremental projection is structural, not
    hash-skipped.
    """
    repo: ObjectRepository = SQLAlchemyObjectRepository(session)
    documents = repo.find_by_type(ObjectType.DOCUMENT)
    indexed = 0
    skipped = 0
    chunked = 0
    content_rows: list[DocumentContentModel] = []
    chunk_rows: list[DocumentChunkModel] = []
    # P1: FTS rows + identity entries derived from the SAME objects/content.
    fts_rows: list[dict] = []
    identity_entries: list[dict] = []

    for doc in documents:
        text, source_item_id = _resolve_text(repo, storage, doc)
        if not text:
            skipped += 1
            continue
        h = content_hash(text)
        content_rows.append(
            DocumentContentModel(
                object_id=str(doc.id),
                version=doc.version,
                content_text=text,
                content_hash=h,
                source_item_id=source_item_id,
                created_at=_utcnow_iso(),
            )
        )
        indexed += 1
        # P1: FTS row (title/metadata from the object snapshot — same
        # derivation as the applier) and identity entry (content hash).
        search_doc = to_search_document(SnapshotMapper.to_snapshot(doc))
        fts_rows.append(
            {
                "object_id": str(doc.id),
                "object_type": ObjectType.DOCUMENT.value,
                "version": doc.version,
                "title": search_doc.title,
                "metadata_text": search_doc.metadata_text,
                "content_text": text,
            }
        )
        identity_entries.append({"object_id": str(doc.id), "content_hash": h})
        chunks = chunk_text(text)
        if not chunks:
            continue
        chunked += 1
        now = _utcnow_iso()
        for index, chunk in enumerate(chunks):
            chunk_rows.append(
                DocumentChunkModel(
                    document_id=str(doc.id),
                    chunk_index=index,
                    content=chunk.content,
                    char_start=chunk.start,
                    char_end=chunk.end,
                    token_count=chunk.token_count,
                    content_hash=content_hash(chunk.content),
                    version=doc.version,
                    source_item_id=source_item_id or None,
                    created_at=now,
                )
            )

    def write() -> None:
        session.execute(delete(DocumentContentModel))
        session.execute(delete(DocumentChunkModel))
        session.execute(delete(DocumentIdentityModel))
        for row in content_rows:
            session.add(row)
        for row in chunk_rows:
            session.add(row)
        # P1: rebuild the identity registry in the SAME transaction
        # (deterministic canonical = smallest object_id per content hash).
        SQLDocumentIdentityStore(session).recompute(identity_entries)
        # P1: rebuild the FTS projection for the documents being rebuilt —
        # ownership-scoped (delete_many of exactly these rows, never rows
        # owned by other objects). Graceful: a missing FTS table (pre-0011)
        # logs once and degrades to the LIKE path.
        try:
            fts = SQLFTSRepository(session)
            fts.delete_many([row["object_id"] for row in fts_rows])
            for row in fts_rows:
                doc_chunks = [c for c in chunk_rows if c.document_id == row["object_id"]]
                fts.upsert(
                    object_id=row["object_id"],
                    object_type=row["object_type"],
                    version=row["version"],
                    title=row["title"],
                    metadata_text=row["metadata_text"],
                    content_text=row["content_text"],
                    chunks_text="\n".join(c.content for c in doc_chunks),
                )
        except _OperationalError:
            _log.warning(
                "document_search_fts table missing; FTS rebuild degraded "
                "(run alembic upgrade head / init_db)."
            )

    commit_with_retry(session, write)
    duplicates = sum(
        1
        for entries in _group_by_hash(identity_entries).values()
        if len(entries) > 1 for oid in entries if oid != min(entries)
    )
    return {
        "indexed": indexed,
        "skipped": skipped,
        "chunked": chunked,
        "duplicates": duplicates,
    }


def _resolve_text(repo, storage, doc) -> tuple[str | None, str]:
    """Authoritative extracted text for one document.

    Resolution order (mirrors the incremental writers):
    1. intake origin: BELONGS_TO -> INTAKE_ITEM -> extraction descriptor
       ``text_key`` -> blob (source of truth for intake documents);
    2. P0 direct-upload origin: the stored blob at the ``file_path``
       metadata key, parsed with the existing parser registry (fixes the
       verified rebuild gap where direct uploads were silently skipped).
    """
    item_ids = [
        rel.target
        for rel in doc.relationships
        if rel.kind is RelationshipKind.BELONGS_TO
    ]
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
            continue
        if text:
            return text, str(item_id)
    # Direct upload: stored blob -> parse -> text.
    file_path = doc.metadata.get_value(KEY_FILE_PATH)
    file_name = doc.metadata.get_value(KEY_FILE_NAME) or ""
    if not file_path or not storage.exists(file_path):
        return None, ""
    extension = file_name.rsplit(".", 1)[-1] if "." in file_name else ""
    parser = build_document_parsers().get(format_of(extension) or "")
    if parser is None:
        return None, ""
    try:
        blob = storage.read(file_path)
        result = parser.parse(blob)
    except Exception:  # noqa: BLE001 — unparsable direct upload skips
        _log.warning(
            "Content rebuild: cannot parse direct-upload blob %r for %s",
            file_path, doc.id,
        )
        return None, ""
    text = (result.text or "").strip()
    if not text:
        return None, ""
    return text, ""


def _group_by_hash(entries):
    from collections import defaultdict

    by_hash: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        if entry.get("content_hash"):
            by_hash[entry["content_hash"]].append(entry["object_id"])
    return dict(by_hash)


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
