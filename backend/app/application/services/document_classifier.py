"""Deterministic document classifier (V3 M6 ADR-053, extended ADR-067).

Classifies a document's semantic type(s) from text + filename using
deterministic rules only (filename > heading > issuer), and returns a PRIMARY
type plus SECONDARY types with per-type confidence — one document can match
multiple types (a conference certificate is also a participation + maybe an
award). No strong model is consulted; low/ambiguous matches return ``unknown``
rather than inventing a type.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.knowledge.document_types import DOCUMENT_TYPES, DocumentTypeSpec

_HEADING_LINES = 12
_CONFIDENCE = {"filename": 0.95, "heading": 0.9, "issuer": 0.8}
#: A classification is "high confidence" at/above this threshold.
HIGH_CONFIDENCE = 0.8


@dataclass(frozen=True)
class TypeMatch:
    type_id: str
    confidence: float
    method: str


@dataclass(frozen=True)
class ClassificationResult:
    document_type_id: str | None
    confidence: float
    method: str  # "filename" | "heading" | "issuer" | "unknown"
    secondary_types: tuple[TypeMatch, ...] = field(default_factory=tuple)
    evidence: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_high_confidence(self) -> bool:
        return self.document_type_id is not None and self.confidence >= HIGH_CONFIDENCE

    def all_types(self) -> tuple[str, ...]:
        """Primary + secondary type ids (primary first)."""
        ids = [self.document_type_id] if self.document_type_id else []
        ids += [m.type_id for m in self.secondary_types if m.type_id not in ids]
        return tuple(ids)


def _matches(spec: DocumentTypeSpec, text: str, patterns: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(p.casefold() in lowered for p in patterns)


class DocumentClassifier:
    """Classify a document's semantic type(s) deterministically.

    Scoring is specificity-weighted: filename matches outweigh heading
    outweigh issuer, and within a stage a type matching MORE keywords is more
    specific. The highest-scoring type is PRIMARY; every other match is a
    SECONDARY type. This lets one document legitimately map to multiple types
    (a certificate of participation is also a conference + participation),
    while a generic type (e.g. "correspondence") never beats a specific one
    (e.g. "grant_sanction_letter") on a mere "letter" substring.
    """

    #: Stage weights (filename > heading > issuer).
    _WEIGHTS = {"filename": 3, "heading": 2, "issuer": 1}

    def classify(self, text: str, filename: str = "") -> ClassificationResult:
        body = text or ""
        heading = "\n".join(body.splitlines()[: _HEADING_LINES])

        scored: dict[str, float] = {}
        methods: dict[str, str] = {}
        for method, haystack, getter in (
            ("filename", filename, lambda s: s.filename_patterns),
            ("heading", heading, lambda s: s.heading_keywords),
            ("issuer", body, lambda s: s.issuer_keywords),
        ):
            for spec in DOCUMENT_TYPES:
                patterns = getter(spec)
                if not patterns:
                    continue
                hits = sum(1 for p in patterns if p.casefold() in haystack.casefold())
                if hits:
                    scored[spec.type_id] = scored.get(spec.type_id, 0.0) + self._WEIGHTS[method] * hits
                    # keep the strongest (highest-weight) stage as the method
                    if spec.type_id not in methods or self._WEIGHTS[method] > self._WEIGHTS.get(methods[spec.type_id], 0):
                        methods[spec.type_id] = method

        if not scored:
            return ClassificationResult(None, 0.0, "unknown")

        ordered = sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))
        primary_id = ordered[0][0]
        secondary = tuple(
            TypeMatch(tid, self._confidence(tid, scored[tid], methods[tid]), methods[tid])
            for tid, _ in ordered[1:]
        )
        return ClassificationResult(
            document_type_id=primary_id,
            confidence=self._confidence(primary_id, scored[primary_id], methods[primary_id]),
            method=methods[primary_id],
            secondary_types=secondary,
            evidence=tuple(f"{methods[tid]}:{tid}" for tid, _ in ordered),
        )

    @staticmethod
    def _confidence(type_id: str, score: float, method: str) -> float:
        # map a weighted specificity score back onto the 0..1 confidence band
        # anchored at the per-stage confidence, capped at 0.97.
        base = _CONFIDENCE[method]
        bonus = min(score * 0.02, 0.07)
        return round(min(base + bonus, 0.97), 3)


__all__ = [
    "HIGH_CONFIDENCE",
    "ClassificationResult",
    "DocumentClassifier",
    "TypeMatch",
]
