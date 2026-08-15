"""Search result DTO with provenance (Sprint-5 M2).

``SearchHit`` is what the search use case returns: the core projection
fields plus deterministic provenance — which index leg produced the hit
(``index_source``: lexical / semantic / both) and the deterministic
reciprocal-rank-fusion score.
"""
from __future__ import annotations

from dataclasses import dataclass

INDEX_SOURCE_LEXICAL = "lexical"
INDEX_SOURCE_SEMANTIC = "semantic"
INDEX_SOURCE_BOTH = "both"


@dataclass(frozen=True)
class SearchHit:
    object_id: str
    object_type: str
    title: str
    version: int
    index_source: str  # INDEX_SOURCE_* constant
    score: float  # deterministic reciprocal-rank-fusion score
    # P0-2: the deterministic ``key: value`` metadata text of the object
    # (from the search projection). Additive — the search API route does not
    # serialize it; the AI retrieval layer uses it as LLM evidence.
    metadata_text: str = ""
