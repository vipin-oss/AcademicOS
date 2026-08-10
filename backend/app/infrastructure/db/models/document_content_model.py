"""ORM model: the document-content search projection (M27).

Derived data only — the extracted-text blob in file storage remains the
source of truth; this row is a searchable, rebuildable projection. Keyed by
the owning DOCUMENT object id; ``version`` is the document's version at
write time; ``source_item_id`` records the intake item the text came from
(provenance + deterministic rebuild).
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text

from app.infrastructure.db.models.object_model import Base


class DocumentContentModel(Base):
    __tablename__ = "document_contents"

    object_id = Column(String, primary_key=True)
    version = Column(Integer, nullable=False)
    content_text = Column(Text, nullable=False)
    source_item_id = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
