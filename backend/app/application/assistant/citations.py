"""Citation Builder (Sprint-6 M3 Phase 3).

The single owner of citation construction: turns the permission-filtered
retrieval items into numbered, deduplicated, stably-ordered
``AssistantCitation`` records and renders their evidence cards.

- Deterministic numbering: 1..n in the retrieval order (itself
  deterministic — search RRF order then graph BFS order).
- Deduplication: one citation per object_id (first occurrence kept).
- Stable identifiers: ``object_id`` is the permanent citation id; the
  number is a per-turn index, deterministic for the same retrieval.
- Evidence cards reuse the shared href table (``links.href_for``) — the
  same navigation the provider cards use, never duplicated.

No provider logic, no retrieval logic — pure presentation of facts that
already exist on the retrieval items.
"""
from __future__ import annotations

from collections.abc import Iterable

from app.application.assistant.links import href_for
from app.application.dtos.assistant import (
    AssistantCardOutput,
    AssistantCitation,
    RetrievedItem,
)


class CitationBuilder:
    """Deterministic evidence numbering + card rendering."""

    def build(
        self, retrieved: Iterable[RetrievedItem]
    ) -> tuple[AssistantCitation, ...]:
        """Number the retrieved items 1..n, deduplicated by object_id."""
        seen: set[str] = set()
        citations: list[AssistantCitation] = []
        for item in retrieved:
            if item.object_id in seen:
                continue
            seen.add(item.object_id)
            citations.append(
                AssistantCitation(
                    number=len(citations) + 1,
                    object_id=item.object_id,
                    object_type=item.object_type,
                    title=item.title,
                    sources=item.sources,
                    version=item.version,
                    score=item.score,
                )
            )
        return tuple(citations)

    def evidence_cards(
        self, citations: Iterable[AssistantCitation]
    ) -> list[AssistantCardOutput]:
        """One navigable card per citation (shared href table)."""
        return [
            AssistantCardOutput(
                object_id=citation.object_id,
                object_type=citation.object_type,
                title=citation.title,
                subtitle=citation.object_type.replace("_", " "),
                href=href_for(citation.object_type, citation.object_id),
            )
            for citation in citations
        ]
