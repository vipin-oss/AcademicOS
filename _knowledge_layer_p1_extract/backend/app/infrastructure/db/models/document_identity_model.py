"""ORM model: the document-identity registry (P1 Knowledge-Layer Scale).

Derived data only — the DOCUMENT objects remain authoritative; this table
materializes the identity signal (``content_hash`` = sha256 of the
NORMALIZED extracted text) for deterministic duplicate detection.

Identity semantics (never filename, never version):
- ``content_hash`` is the identity key: two documents with the same
  normalized text are the same CONTENT regardless of filename.
- ``canonical_document_id`` is the DETERMINISTIC canonical representative:
  the document with the smallest object_id among those sharing the hash
  (stable under rebuild; deleting the canonical recomputes it to the next).
- ``document_count`` is the number of documents sharing this content
  (the original + duplicates/aliases).

Rebuildable: the rebuild recomputes every row from the content projections
(delete-all + re-insert with the same deterministic canonical rule), so
incremental == rebuilt always.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String

from app.infrastructure.db.models.object_model import Base


class DocumentIdentityModel(Base):
    __tablename__ = "document_registry"

    content_hash = Column(String, primary_key=True)
    canonical_document_id = Column(String, nullable=False)
    document_count = Column(Integer, nullable=False, default=1)
    updated_at = Column(String, nullable=False)
