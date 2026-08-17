"""SQL implementation of the document-identity registry store (P1).

Mirrors the content/chunk stores: explicit dialect-agnostic writes, no
commits here — the caller (the outbox applier / rebuild) owns the
transaction. Canonical = smallest object_id per content hash (deterministic,
stable under rebuild).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.application.ports.document_identity_store import DocumentIdentityStore
from app.infrastructure.db.models.document_identity_model import DocumentIdentityModel


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class SQLDocumentIdentityStore(DocumentIdentityStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def sync_document(self, *, content_hash: str, object_id: str) -> None:
        row = self._session.get(DocumentIdentityModel, content_hash)
        if row is None:
            # Use merge() instead of add() to handle duplicate content_hash
            # within the same uncommitted batch (idempotent upsert).
            self._session.merge(
                DocumentIdentityModel(
                    content_hash=content_hash,
                    canonical_document_id=object_id,
                    document_count=1,
                    updated_at=_utcnow_iso(),
                )
            )
            return
        group = self.group(content_hash)
        row.canonical_document_id = min(group) if group else object_id
        row.document_count = len(group)
        row.updated_at = _utcnow_iso()

    def remove_document(self, *, content_hash: str, object_id: str) -> None:
        row = self._session.get(DocumentIdentityModel, content_hash)
        if row is None:
            return
        group = [oid for oid in self.group(content_hash) if oid != object_id]
        if not group:
            self._session.delete(row)
            return
        row.canonical_document_id = min(group)
        row.document_count = len(group)
        row.updated_at = _utcnow_iso()

    def canonical_for(self, content_hash: str) -> str | None:
        row = self._session.get(DocumentIdentityModel, content_hash)
        return row.canonical_document_id if row is not None else None

    def group(self, content_hash: str) -> list[str]:
        from app.infrastructure.db.models.document_content_model import (
            DocumentContentModel,
        )

        rows = self._session.execute(
            select(DocumentContentModel.object_id).where(
                DocumentContentModel.content_hash == content_hash
            )
        ).scalars().all()
        return sorted(str(oid) for oid in rows)

    def recompute(self, entries: list[dict]) -> None:
        """Rebuild the registry from content projections (delete-all +
        re-insert; deterministic canonical = smallest object_id per hash)."""
        by_hash: dict[str, list[str]] = {}
        for entry in entries:
            h = entry["content_hash"]
            oid = entry["object_id"]
            if not h:
                continue
            by_hash.setdefault(h, []).append(oid)
        # Execute DELETE and flush to clear ORM identity map before re-inserting
        self._session.execute(delete(DocumentIdentityModel))
        self._session.flush()
        now = _utcnow_iso()
        for h, ids in by_hash.items():
            ids = sorted(ids)
            # Use merge() for idempotent upsert (handles duplicate hashes
            # within the same batch).
            self._session.merge(
                DocumentIdentityModel(
                    content_hash=h,
                    canonical_document_id=ids[0],
                    document_count=len(ids),
                    updated_at=now,
                )
            )

    def duplicate_count(self) -> int:
        from app.infrastructure.db.models.document_content_model import (
            DocumentContentModel,
        )

        rows = self._session.execute(
            select(
                DocumentContentModel.content_hash,
                DocumentContentModel.object_id,
            ).where(DocumentContentModel.content_hash.isnot(None))
        ).all()
        by_hash: dict[str, list[str]] = {}
        for h, oid in rows:
            by_hash.setdefault(h, []).append(str(oid))
        return sum(
            1
            for ids in by_hash.values()
            if len(ids) > 1 for oid in ids if oid != min(ids)
        )
