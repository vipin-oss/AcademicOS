"""ORM model: the document-chunk search projection (P0 knowledge projection).

Derived data only — the document object (and its extracted-content
projection) is authoritative; chunk rows are a deterministic, rebuildable,
searchable segmentation of the normalized extracted text. Keyed by the
owning DOCUMENT object id + chunk index (a document can never have two
versions of the same chunk — stale rows are replaced, never coexisting).
``content_hash`` is the sha256 of the chunk content (normalized); the row
``version`` is the document version at write time (optimistic/version-safe
writes only — never a content-change authority).
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text

from app.infrastructure.db.models.object_model import Base


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"

    document_id = Column(String, primary_key=True)
    chunk_index = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=False)
    content_hash = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    source_item_id = Column(String, nullable=True)
    created_at = Column(String, nullable=False)
